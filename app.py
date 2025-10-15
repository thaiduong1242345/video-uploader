import os
import re
import json
import uuid
import queue
import threading
import subprocess
from datetime import timedelta
from typing import Tuple, Optional

from dotenv import load_dotenv
from flask import Flask, request, jsonify, redirect, session, Response
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Google OAuth libs
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv()

# ===== ENV =====
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "http://localhost:3000")
OAUTH_REDIRECT_URI = os.environ.get("OAUTH_REDIRECT_URI", "http://localhost:8080/api/auth/callback")
GOOGLE_CLIENT_SECRETS_FILE = os.environ.get("GOOGLE_CLIENT_SECRETS_FILE", "credentials/client_secret.json")

RCLONE_BIN = os.environ.get("RCLONE_BIN", "rclone")
RCLONE_CONFIG_PATH = os.environ.get("RCLONE_CONFIG_PATH", "./rclone/rclone.conf")
RCLONE_REMOTE_NAME = os.environ.get("RCLONE_REMOTE_NAME", "gdrive")
RCLONE_DEST_PATH = os.environ.get("RCLONE_DEST_PATH", "AutoUploads")
RCLONE_TRANSFERS = os.environ.get("RCLONE_TRANSFERS", "4")
RCLONE_CHECKERS = os.environ.get("RCLONE_CHECKERS", "8")
RCLONE_DRIVE_CHUNK_SIZE = os.environ.get("RCLONE_DRIVE_CHUNK_SIZE", "64M")
RCLONE_DELETE_LOCAL = os.environ.get("RCLONE_DELETE_LOCAL", "0") == "1"

MAX_MB = int(os.environ.get("MAX_UPLOAD_MB", "20480"))

# ===== Dirs =====
os.makedirs(os.path.dirname(RCLONE_CONFIG_PATH), exist_ok=True)
UPLOADS_DIR = "./uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)

# ===== Flask app =====
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")
app.permanent_session_lifetime = timedelta(days=7)
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024

CORS(
    app,
    supports_credentials=True,
    resources={r"/api/*": {"origins": [FRONTEND_BASE_URL]}},
)

# ===== Google OAuth helpers =====
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/drive.file",
]

def build_flow() -> Flow:
    return Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=OAUTH_REDIRECT_URI,
    )

def get_user_email(creds: Credentials) -> str:
    oauth2 = build("oauth2", "v2", credentials=creds)
    info = oauth2.userinfo().get().execute()
    return info.get("email")

def read_client_id_secret(path: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Đọc client_id/client_secret trong credentials .json (type: web).
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        web = data.get("web") or data.get("installed")
        return web.get("client_id"), web.get("client_secret")
    except Exception:
        return None, None

def rclone_remote_exists() -> bool:
    res = subprocess.run(
        [RCLONE_BIN, "--config", RCLONE_CONFIG_PATH, "listremotes"],
        capture_output=True, text=True
    )
    return res.returncode == 0 and f"{RCLONE_REMOTE_NAME}:" in res.stdout

def ensure_remote_created_from_creds(creds: Credentials) -> bool:
    """
    Tạo remote rclone từ Google Credentials (Flask OAuth).
    Quan trọng: phải set client_id/client_secret giống app OAuth để refresh token hợp lệ.
    """
    token_json = {
        "access_token": creds.token,
        "token_type": "Bearer",
        "refresh_token": creds.refresh_token,
        "expiry": creds.expiry.isoformat().replace("+00:00", "Z") if creds.expiry else None,
    }
    client_id, client_secret = read_client_id_secret(GOOGLE_CLIENT_SECRETS_FILE)

    # Xoá remote cũ cùng tên (idempotent)
    subprocess.run(
        [RCLONE_BIN, "--config", RCLONE_CONFIG_PATH, "config", "delete", RCLONE_REMOTE_NAME],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    cmd = [
        RCLONE_BIN, "--config", RCLONE_CONFIG_PATH,
        "config", "create", RCLONE_REMOTE_NAME, "drive",
        "scope=drive.file",
        f"token={json.dumps(token_json)}",
    ]
    if client_id:   cmd.append(f"client_id={client_id}")
    if client_secret: cmd.append(f"client_secret={client_secret}")

    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode == 0

# ===== Auth routes (Flask OAuth) =====
@app.get("/api/auth/login")
def auth_login():
    flow = build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    session["oauth_state"] = state
    return redirect(auth_url)

@app.get("/api/auth/callback")
def auth_callback():
    state = session.get("oauth_state")
    if not state:
        return redirect(FRONTEND_BASE_URL + "/?authError=missing_state")

    flow = build_flow()
    try:
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        email = get_user_email(creds)
    except Exception as e:
        return redirect(FRONTEND_BASE_URL + f"/?authError={str(e)}")

    if not ensure_remote_created_from_creds(creds):
        return redirect(FRONTEND_BASE_URL + "/?authError=rclone_config_failed")

    session["email"] = email
    return redirect(FRONTEND_BASE_URL + "/auth/success")

@app.get("/api/auth/me")
def auth_me():
    email = session.get("email")
    return jsonify({"logged_in": bool(email), "email": email})

@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})

# ===== rclone remote status =====
@app.get("/api/rclone/remote/status")
def rclone_remote_status():
    return jsonify({"configured": rclone_remote_exists(), "remote": RCLONE_REMOTE_NAME})

# ===== Upload + SSE progress =====
upload_sessions = {}  # upload_id -> dict(queue, local_path, filename, dest_folder, dest_object_path, total_bytes)

def rclone_lsjson_get_id(dest_folder: str, filename: str):
    """
    Lấy file ID qua rclone lsjson để tạo link xem.
    """
    res = subprocess.run(
        [RCLONE_BIN, "--config", RCLONE_CONFIG_PATH, "lsjson", dest_folder, "--files-only", "--max-depth", "1"],
        capture_output=True, text=True
    )
    if res.returncode != 0:
        return None, None
    try:
        arr = json.loads(res.stdout)
        for o in arr:
            name = o.get("Name") or o.get("Path")
            if name == filename:
                file_id = o.get("ID")
                if file_id:
                    link = f"https://drive.google.com/file/d/{file_id}/view?usp=drivesdk"
                    return file_id, link
    except Exception:
        pass
    return None, None

def run_rclone_copy_stream(upload_id: str):
    sess = upload_sessions[upload_id]
    q: queue.Queue = sess["queue"]
    local_path: str = sess["local_path"]
    filename: str = sess["filename"]
    dest_folder: str = sess["dest_folder"]
    dest_object: str = sess["dest_object_path"]

    total = os.path.getsize(local_path)
    sess["total_bytes"] = total

    cmd = [
        RCLONE_BIN, "--config", RCLONE_CONFIG_PATH,
        "copyto", local_path, dest_object,
        "--use-json-log",
        "--progress",
        "--stats=1s",
        "--transfers", RCLONE_TRANSFERS,
        "--checkers",   RCLONE_CHECKERS,
        "--drive-chunk-size", RCLONE_DRIVE_CHUNK_SIZE,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

    def push(ev: dict):
        try: q.put_nowait(ev)
        except: pass

    push({"event": "start", "filename": filename, "total": total})

    try:
        # rclone JSON log ở STDERR
        for line in proc.stderr:
            line = line.strip()
            if not line: continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            stats = obj.get("stats")
            if stats:
                transferred = int(stats.get("bytes", 0))
                speed = float(stats.get("speed", 0.0))
                eta = stats.get("eta", 0)
                pct = round(transferred * 100.0 / total, 2) if total > 0 else 0.0
                push({"event": "progress", "bytes": transferred, "total": total, "pct": pct, "speed": speed, "eta": eta})

            if obj.get("msg", "").startswith("Copied") and obj.get("object") == filename:
                push({"event": "file_copied", "filename": filename})
    finally:
        proc.wait()

    file_id, link = rclone_lsjson_get_id(dest_folder, filename)
    if RCLONE_DELETE_LOCAL:
        try: os.remove(local_path)
        except: pass

    push({"event": "done", "ok": True, "file_id": file_id, "webViewLink": link})
    push({"event": "close"})

@app.post("/api/upload")
def api_upload():
    if not rclone_remote_exists():
        return jsonify({"error": "Drive remote is not configured"}), 400

    f = request.files.get("file")
    if not f or f.filename == "":
        return jsonify({"error": "No file"}), 400

    filename = secure_filename(f.filename)
    local_path = os.path.join(UPLOADS_DIR, filename)
    f.save(local_path)

    dest_folder = f"{RCLONE_REMOTE_NAME}:{RCLONE_DEST_PATH}" if RCLONE_DEST_P
ATH else f"{RCLONE_REMOTE_NAME}:"
    dest_object_path = dest_folder.rstrip("/") + "/" + filename

    upload_id = str(uuid.uuid4())
    q: queue.Queue = queue.Queue()
    upload_sessions[upload_id] = {
        "queue": q,
        "local_path": local_path,
        "filename": filename,
        "dest_folder": dest_folder,
        "dest_object_path": dest_object_path,
        "total_bytes": None,
    }
    threading.Thread(target=run_rclone_copy_stream, args=(upload_id,), daemon=True).start()

    return jsonify({"upload_id": upload_id, "filename": filename, "dest_folder": dest_folder, "dest_object_path": dest_object_path})

@app.get("/api/upload/stream")
def api_upload_stream():
    upload_id = request.args.get("upload_id")
    if not upload_id or upload_id not in upload_sessions:
        return jsonify({"error": "invalid upload_id"}), 400
    q: queue.Queue = upload_sessions[upload_id]["queue"]

    def gen():
        while True:
            msg = q.get()
            yield f"data: {json.dumps(msg)}\n\n"
            if msg.get("event") in ("done", "close", "error"):
                break

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return Response(gen(), headers=headers)

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=DEBUG)

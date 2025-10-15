"use client";

import { useRef, useState } from "react";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL!;

export default function UploadBox() {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [result, setResult] = useState<{ ok?: boolean; out?: string; err?: string; dest?: string }>({});

  const onChoose = () => inputRef.current?.click();

  const onFile = (f?: File) => {
    if (!f) return;
    setFile(f);
    setProgress(0);
    setResult({});
  };

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) onFile(e.dataTransfer.files[0]);
  };

  const upload = async () => {
    if (!file) return;
    setProgress(0);
    setResult({});
    await new Promise<void>((resolve) => {
      const form = new FormData();
      form.append("file", file);
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${BACKEND}/api/upload`, true);
      xhr.withCredentials = true;
      xhr.upload.onprogress = (evt) => {
        if (evt.lengthComputable) {
          setProgress(Math.round((evt.loaded / evt.total) * 100));
        }
      };
      xhr.onload = () => {
        try {
          const d = JSON.parse(xhr.responseText);
          setResult({
            ok: d.ok,
            out: d.stdout,
            err: d.error || d.stderr,
            dest: d.dest,
          });
        } catch (e: any) {
          setResult({ ok: false, err: e?.message || "Parse error" });
        }
        resolve();
      };
      xhr.onerror = () => {
        setResult({ ok: false, err: "Network error" });
        resolve();
      };
      xhr.send(form);
    });
  };

  return (
    <div className="card">
      <h3>Upload file lên Drive (rclone copy)</h3>
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={onDrop}
        style={{
          border: "2px dashed #d1d5db",
          borderRadius: 12,
          padding: 24,
          textAlign: "center",
          cursor: "pointer",
        }}
        onClick={onChoose}
      >
        {file ? (
          <>
            <p><strong>{file.name}</strong> ({(file.size / 1024 / 1024).toFixed(2)} MB)</p>
            <p className="muted">Nhấn “Bắt đầu upload”.</p>
          </>
        ) : (
          <>
            <p>Kéo-thả file vào đây hoặc nhấn để chọn</p>
            <p className="muted">Upload từ trình duyệt → server → rclone copy → Drive.</p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          hidden
          onChange={(e) => onFile(e.target.files?.[0] || undefined)}
        />
      </div>

      <div className="space" />

      <div className="row" style={{ justifyContent: "space-between" }}>
        <button className="btn btn-primary" onClick={upload} disabled={!file}>
          Bắt đầu upload
        </button>
        {file && <span className="tag">Đã chọn: {file.name}</span>}
      </div>

      <div className="space" />
      <div className="progress">
        <div className="bar" style={{ width: `${progress}%` }} />
      </div>
      <p className="muted">Tiến độ FE→BE: {progress}%</p>

      {result.ok ? (
        <>
          <p>✅ Upload xong. Đích: <code>{result.dest}</code></p>
          <details>
            <summary>Chi tiết (stdout)</summary>
            <pre style={{ whiteSpace: "pre-wrap" }}>{result.out}</pre>
          </details>
        </>
      ) : result.err ? (
        <p style={{ color: "#b00020" }}>Lỗi: {result.err}</p>
      ) : null}
    </div>
  );
}

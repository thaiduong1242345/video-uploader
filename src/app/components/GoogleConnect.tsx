"use client";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL!;

import { useEffect, useState } from "react";

type Me = { logged_in: boolean; email?: string };
type RemoteStatus = { configured: boolean; remote: string };

export default function GoogleConnect() {
  const [me, setMe] = useState<Me>({ logged_in: false });
  const [rs, setRs] = useState<RemoteStatus>({ configured: false, remote: "gdrive" });

  const refresh = async () => {
    const a = await fetch(`${BACKEND}/api/auth/me`, { credentials: "include" });
    setMe(await a.json());
    const b = await fetch(`${BACKEND}/api/rclone/remote/status`, { credentials: "include" });
    setRs(await b.json());
  };

  useEffect(() => { refresh(); }, []);

  const login = () => {
    // Redirect thẳng tới backend -> Google
    window.location.href = `${BACKEND}/api/auth/login`;
  };

  const logout = async () => {
    await fetch(`${BACKEND}/api/logout`, { method: "POST", credentials: "include" });
    refresh();
  };

  return (
    <div className="card">
      <h3>Kết nối Google Drive (Flask OAuth)</h3>
      {me.logged_in ? (
        <>
          <p>Đã đăng nhập: <strong>{me.email}</strong></p>
          <p>rclone remote: {rs.configured ? `✅ ${rs.remote}` : "❌ chưa cấu hình"}</p>
          <button className="btn btn-ghost" onClick={logout}>Đăng xuất</button>
        </>
      ) : (
        <>
          <p className="muted">Nhấn để đăng nhập Google Drive (mở trên điện thoại/thiết bị bất kỳ trong LAN đều ok).</p>
          <button className="btn btn-primary" onClick={login}>Đăng nhập Google Drive</button>
        </>
      )}
    </div>
  );
}

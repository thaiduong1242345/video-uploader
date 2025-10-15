import RcloneConnect from "@/app/components/GoogleConnect";
import UploadBox from "@/app/components/UploadBox";

export default function Page() {
  return (
    <div className="container">
      <h2>LAN → Google Drive (rclone OAuth)</h2>
      <div className="card">
        <p className="muted">
          Bước 1: Kết nối Google Drive (qua rclone). Bước 2: Chọn file và Upload.
          FE sẽ mở tab đăng nhập Google, còn trang này tự động đợi và nhận cấu hình.
        </p>
      </div>
      <RcloneConnect />
      <UploadBox />
    </div>
  );
}

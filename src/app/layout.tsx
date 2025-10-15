export const metadata = { title: "LAN → Drive (rclone)" };

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body>
        {children}

        {/* ✅ Dùng dangerouslySetInnerHTML thay cho styled-jsx */}
        <style
          dangerouslySetInnerHTML={{
            __html: `
              html, body {
                margin: 0;
                padding: 0;
                font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
              }
              .container {
                max-width: 880px;
                margin: 24px auto;
                padding: 0 16px;
              }
              .card {
                border: 1px solid #e5e7eb;
                border-radius: 16px;
                padding: 20px;
                margin: 16px 0;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
              }
              .btn {
                display: inline-block;
                padding: 10px 16px;
                border-radius: 10px;
                text-decoration: none;
                border: 1px solid #111;
                cursor: pointer;
              }
              .btn-primary {
                background: #111;
                color: #fff;
                border-color: #111;
              }
              .btn-ghost {
                background: #fff;
                color: #111;
              }
              .muted {
                color: #6b7280;
                font-size: 14px;
              }
              .row {
                display: flex;
                gap: 12px;
                align-items: center;
              }
              .space {
                height: 8px;
              }
              .progress {
                width: 100%;
                height: 10px;
                background: #f3f4f6;
                border-radius: 999px;
                overflow: hidden;
              }
              .bar {
                height: 100%;
                background: #111;
                transition: width 0.2s ease;
              }
              .tag {
                font-size: 12px;
                padding: 2px 8px;
                background: #f3f4f6;
                border-radius: 999px;
              }
            `,
          }}
        />
      </body>
    </html>
  );
}

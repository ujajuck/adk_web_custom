// app/layout.tsx
import "./globals.css";
import AppShell from "@/components/shell/AppShell";
import { WorkspaceProvider } from "@/components/workspace/WorkspaceContext";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>
        <WorkspaceProvider>
          <AppShell>{children}</AppShell>
        </WorkspaceProvider>
      </body>
    </html>
  );
}

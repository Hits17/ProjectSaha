import { SessionBoundary } from "@/components/session-boundary";
import type { Metadata } from "next";
import "./fonts.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Saha Admin Console",
  description: "Community, research and platform administration for Saha",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased"><SessionBoundary>{children}</SessionBoundary></body>
    </html>
  );
}

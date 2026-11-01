import type { Metadata } from "next";
import "./fonts.css";
import "./globals.css";
import { AppShell } from "@/components/app-shell";
import { Providers } from "@/components/providers";

export const metadata: Metadata = {
  title: "Saha — Open Innovation",
  description: "Discover documented inventions, connect with institutions and build open projects together.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">
        <Providers><AppShell>{children}</AppShell></Providers>
      </body>
    </html>
  );
}

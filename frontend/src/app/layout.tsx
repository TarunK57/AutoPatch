import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AutoPatch - Autonomous Bug Detection & Verified Repair",
  description:
    "Autonomous developer tool that ingests repositories, detects flaws with multi-agent consensus, isolates root causes with stratified retrieval, generates minimal patches, and verifies them in sandboxed Docker containers before human approval.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-slate-50 dark:bg-[#090d16] text-slate-900 dark:text-slate-100 antialiased selection:bg-indigo-500 selection:text-white">
        {children}
      </body>
    </html>
  );
}

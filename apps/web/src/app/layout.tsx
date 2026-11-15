import * as React from "react";
import type { Metadata } from "next";
import { AppLayout } from "@/components/layout/app-layout";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

export const metadata: Metadata = {
  title: "JobAgent AI — L0 Application Platform",
  description: "Autonomous, deterministic-first, human-in-the-loop personal job application assistant.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="h-full bg-slate-50 text-slate-900 font-sans">
        <React.Suspense fallback={<div className="h-screen w-full bg-slate-50" />}>
          <AppLayout>{children}</AppLayout>
        </React.Suspense>
        <Toaster />
      </body>
    </html>
  );
}

import * as React from "react";
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { AppLayout } from "@/components/layout/app-layout";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

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
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="h-full bg-slate-50 text-slate-900">
        <React.Suspense fallback={<div className="h-screen w-full bg-slate-50" />}>
          <AppLayout>{children}</AppLayout>
        </React.Suspense>
        <Toaster />
      </body>
    </html>
  );
}

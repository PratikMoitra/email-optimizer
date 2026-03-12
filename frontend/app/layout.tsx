import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Email Optimizer — AI-Powered Outreach",
  description:
    "Automate your cold email campaigns with AI-personalized sequences, lead validation, and real-time analytics.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AppShell } from "@/components/AppShell";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "NVIDIA Radar — Inception Intelligence v2.1",
  description:
    "Multi-agent platform to attract, qualify, and nurture AI-native startups for NVIDIA Inception Brazil.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="pt-BR"
      className={`${inter.variable} ${jetbrains.variable} dark`}
    >
      <body className="font-sans antialiased bg-bg-base text-text-primary">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}

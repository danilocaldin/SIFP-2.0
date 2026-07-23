import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { Sidebar } from "@/components/sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sifra — Inteligência Financeira Pessoal",
  description: "Como você está financeiramente, agora.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="pt-BR"
      className={`${GeistSans.variable} ${GeistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full bg-background text-foreground">
        <Sidebar />
        <div className="flex min-h-full flex-1 flex-col overflow-x-hidden">{children}</div>
      </body>
    </html>
  );
}

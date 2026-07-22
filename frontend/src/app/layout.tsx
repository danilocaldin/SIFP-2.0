import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { NavBar } from "@/components/nav-bar";
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
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <NavBar />
        {children}
      </body>
    </html>
  );
}

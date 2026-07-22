"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Resumo" },
  { href: "/upload", label: "Upload" },
  { href: "/revisao", label: "Revisão" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/patrimonio", label: "Patrimônio" },
  { href: "/orcamento", label: "Orçamento" },
  { href: "/projecoes", label: "Projeções" },
  { href: "/diagnosticos", label: "Diagnósticos" },
  { href: "/relatorio", label: "Relatório" },
  { href: "/chat", label: "Chat" },
];

export function NavBar() {
  const pathname = usePathname();

  return (
    <header className="border-b border-border">
      <nav className="mx-auto flex w-full max-w-3xl items-center gap-6 px-6 py-4">
        <Link href="/" className="flex items-center gap-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/icon.svg" alt="" width={22} height={22} className="rounded-[5px]" />
          <span className="font-display text-[17px] font-semibold tracking-tight text-foreground">
            Sifra
          </span>
        </Link>
        <div className="flex gap-4">
          {LINKS.map((link) => {
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`text-sm transition-colors ${
                  active
                    ? "font-medium text-primary"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </div>
      </nav>
    </header>
  );
}

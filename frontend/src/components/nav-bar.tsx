"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Resumo" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/diagnosticos", label: "Diagnósticos" },
];

export function NavBar() {
  const pathname = usePathname();

  return (
    <header className="border-b border-border">
      <nav className="mx-auto flex w-full max-w-3xl items-center gap-6 px-6 py-4">
        <span className="text-sm font-semibold">💰 SIFP</span>
        <div className="flex gap-4">
          {LINKS.map((link) => {
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`text-sm transition-colors ${
                  active
                    ? "font-medium text-foreground"
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

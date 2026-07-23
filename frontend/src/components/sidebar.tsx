"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  FileText,
  Home,
  LayoutDashboard,
  ListChecks,
  MessageCircle,
  PiggyBank,
  Stethoscope,
  TrendingUp,
  Upload,
  Wallet,
  type LucideIcon,
} from "lucide-react";

type NavItem = { href: string; label: string; icon: LucideIcon };
type NavGroup = { label: string; items: NavItem[] };

const GROUPS: NavGroup[] = [
  {
    label: "Visão geral",
    items: [
      { href: "/", label: "Resumo", icon: Home },
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    ],
  },
  {
    label: "Dados",
    items: [
      { href: "/upload", label: "Upload", icon: Upload },
      { href: "/revisao", label: "Revisão", icon: ListChecks },
    ],
  },
  {
    label: "Planejamento",
    items: [
      { href: "/patrimonio", label: "Patrimônio", icon: Wallet },
      { href: "/orcamento", label: "Orçamento", icon: PiggyBank },
      { href: "/projecoes", label: "Projeções", icon: TrendingUp },
    ],
  },
  {
    label: "Análise",
    items: [
      { href: "/diagnosticos", label: "Diagnósticos", icon: Stethoscope },
      { href: "/relatorio", label: "Relatório", icon: FileText },
      { href: "/chat", label: "Chat", icon: MessageCircle },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-14 flex-shrink-0 flex-col overflow-y-auto bg-brand-ink px-2 py-5 md:w-60 md:px-4">
      <Link href="/" className="flex items-center justify-center gap-2 px-0 pb-6 md:justify-start md:px-2">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/icon.svg" alt="Sifra" width={26} height={26} className="rounded-[6px]" />
        <span className="hidden font-display text-lg font-semibold tracking-tight text-white md:inline">
          Sifra
        </span>
      </Link>

      <nav className="flex-1 space-y-6">
        {GROUPS.map((group) => (
          <div key={group.label}>
            <p className="hidden px-2 text-[11px] font-medium tracking-wider text-white/40 uppercase md:block">
              {group.label}
            </p>
            <div className="mt-2 space-y-0.5">
              {group.items.map((item) => {
                const active = pathname === item.href;
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    title={item.label}
                    className={`flex items-center justify-center gap-2.5 rounded-md px-0 py-2 text-sm transition-colors md:justify-start md:px-2.5 md:py-1.5 ${
                      active
                        ? "bg-brand-teal/15 font-medium text-brand-teal"
                        : "text-white/65 hover:bg-white/5 hover:text-white"
                    }`}
                  >
                    <Icon size={17} strokeWidth={2} className="flex-shrink-0" />
                    <span className="hidden md:inline">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}

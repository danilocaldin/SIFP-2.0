"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatBRL } from "@/lib/format";
import type { MonthlyEvolution } from "@/lib/types";

const SERIES = [
  { key: "Receitas", color: "var(--chart-receita)" },
  { key: "Despesas", color: "var(--chart-despesa)" },
  { key: "Saldo", color: "var(--chart-saldo)" },
] as const;

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 text-xs shadow-sm">
      <p className="mb-1 font-medium text-foreground">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="flex items-center gap-1.5 text-muted-foreground">
          <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: p.color }} />
          {p.name}: <span className="font-medium text-foreground">{formatBRL(p.value)}</span>
        </p>
      ))}
    </div>
  );
}

export function MonthlyEvolutionChart({ data }: { data: MonthlyEvolution[] }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} barGap={2} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
        <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
        <XAxis
          dataKey="mes_label"
          tick={{ fill: "var(--chart-axis)", fontSize: 12 }}
          axisLine={{ stroke: "var(--chart-grid)" }}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: "var(--chart-axis)", fontSize: 12 }}
          axisLine={false}
          tickLine={false}
          width={40}
        />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--muted)" }} />
        <Legend
          wrapperStyle={{ fontSize: 12, color: "var(--muted-foreground)" }}
          iconType="circle"
          iconSize={8}
        />
        {SERIES.map((s) => (
          <Bar key={s.key} dataKey={s.key} fill={s.color} radius={[4, 4, 0, 0]} maxBarSize={24} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

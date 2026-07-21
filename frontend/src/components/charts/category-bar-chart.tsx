"use client";

import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatBRL } from "@/lib/format";
import type { CategoryBreakdown } from "@/lib/types";

// Rampa sequencial azul, do menor pro maior valor — ver globals.css.
const SEQUENTIAL_STEPS = [
  "var(--chart-seq-0)",
  "var(--chart-seq-1)",
  "var(--chart-seq-2)",
  "var(--chart-seq-3)",
  "var(--chart-seq-4)",
  "var(--chart-seq-5)",
];

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: CategoryBreakdown }[];
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 text-xs shadow-sm">
      <p className="font-medium text-foreground">{row.category}</p>
      <p className="text-muted-foreground">
        {formatBRL(row.value_abs)} ({row.pct.toFixed(0)}%)
      </p>
    </div>
  );
}

export function CategoryBarChart({ data }: { data: CategoryBreakdown[] }) {
  // já vem ordenado do maior pro menor (category_breakdown) — mantém a
  // categoria de maior gasto no topo, como no dashboard Streamlit.
  const chartData = [...data].reverse();
  const n = chartData.length;

  return (
    <ResponsiveContainer width="100%" height={Math.max(200, n * 32)}>
      <BarChart
        data={chartData}
        layout="vertical"
        margin={{ top: 4, right: 48, left: 4, bottom: 4 }}
      >
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="category"
          tick={{ fill: "var(--chart-axis)", fontSize: 12 }}
          axisLine={false}
          tickLine={false}
          width={120}
        />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--muted)" }} />
        <Bar dataKey="value_abs" radius={[0, 4, 4, 0]} maxBarSize={18}>
          {chartData.map((row, i) => {
            const rank = n - 1 - i; // i=0 é o menor valor (revertido) -> rank maior = mais escuro
            const step = Math.round((rank / Math.max(n - 1, 1)) * (SEQUENTIAL_STEPS.length - 1));
            return <Cell key={row.category} fill={SEQUENTIAL_STEPS[step]} />;
          })}
          <LabelList
            dataKey="value_abs"
            position="right"
            fill="var(--muted-foreground)"
            fontSize={12}
            formatter={(value: unknown) => (typeof value === "number" ? formatBRL(value) : String(value ?? ""))}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

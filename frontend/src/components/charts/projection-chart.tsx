"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatBRL } from "@/lib/format";
import type { ProjectionChartPoint } from "@/lib/types";

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

export function ProjectionChart({ data }: { data: ProjectionChartPoint[] }) {
  // Junta histórico e projeção pela mesma data — o backend já repete o
  // último ponto histórico como o primeiro ponto da projeção, então essa
  // data cai na mesma linha com os dois campos preenchidos, e a linha
  // tracejada nasce exatamente onde a sólida termina.
  const byDate = new Map<string, { data: string; historico?: number; projecao?: number }>();
  for (const point of data) {
    const row = byDate.get(point.data) ?? { data: point.data };
    row[point.tipo === "historico" ? "historico" : "projecao"] = point.patrimonio;
    byDate.set(point.data, row);
  }
  const chartData = [...byDate.values()];

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
        <XAxis
          dataKey="data"
          tick={{ fill: "var(--chart-axis)", fontSize: 12 }}
          axisLine={{ stroke: "var(--chart-grid)" }}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: "var(--chart-axis)", fontSize: 12 }}
          axisLine={false}
          tickLine={false}
          width={56}
          tickFormatter={(v: number) => formatBRL(v)}
        />
        <Tooltip content={<ChartTooltip />} cursor={{ stroke: "var(--chart-grid)" }} />
        <Legend wrapperStyle={{ fontSize: 12, color: "var(--muted-foreground)" }} iconType="plainline" />
        <Line
          type="monotone"
          dataKey="historico"
          name="Histórico"
          stroke="var(--chart-saldo)"
          strokeWidth={2}
          dot={{ r: 4, fill: "var(--chart-saldo)", stroke: "var(--card)", strokeWidth: 2 }}
          connectNulls={false}
        />
        <Line
          type="monotone"
          dataKey="projecao"
          name="Projeção"
          stroke="var(--chart-projecao)"
          strokeWidth={2}
          strokeDasharray="6 4"
          dot={{ r: 4, fill: "var(--chart-projecao)", stroke: "var(--card)", strokeWidth: 2 }}
          connectNulls={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

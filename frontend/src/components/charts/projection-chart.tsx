"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatBRL } from "@/lib/format";
import type { ProjectionChartPoint } from "@/lib/types";

type ChartRow = {
  data: string;
  historico?: number;
  projecao?: number;
  melhor?: number;
  pior?: number;
  faixaBase?: number;
  faixaAltura?: number;
};

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string; payload: ChartRow }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const linhas = payload.filter((p) => p.name === "Histórico" || p.name === "Projeção");
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 text-xs shadow-sm">
      <p className="mb-1 font-medium text-foreground">{label}</p>
      {linhas.map((p) => (
        <p key={p.name} className="flex items-center gap-1.5 text-muted-foreground">
          <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: p.color }} />
          {p.name}: <span className="font-medium text-foreground">{formatBRL(p.value)}</span>
        </p>
      ))}
      {row.melhor !== undefined && row.pior !== undefined && (
        <p className="mt-1 border-t border-border pt-1 text-muted-foreground">
          Faixa: {formatBRL(row.pior)} a {formatBRL(row.melhor)}
        </p>
      )}
    </div>
  );
}

export function ProjectionChart({ data }: { data: ProjectionChartPoint[] }) {
  // Junta histórico e projeção pela mesma data — o backend já repete o
  // último ponto histórico como o primeiro ponto da projeção, então essa
  // data cai na mesma linha com os dois campos preenchidos, e a linha
  // tracejada nasce exatamente onde a sólida termina.
  //
  // A faixa (melhor/pior caso) é desenhada com o truque de duas áreas
  // empilhadas: "faixaBase" (transparente, até o valor do pior caso) e
  // "faixaAltura" (visível, do pior até o melhor) — o recharts não tem
  // um jeito nativo de desenhar uma área "entre duas linhas".
  const byDate = new Map<string, ChartRow>();
  for (const point of data) {
    const row = byDate.get(point.data) ?? { data: point.data };
    if (point.tipo === "historico") {
      row.historico = point.patrimonio;
    } else {
      row.projecao = point.patrimonio;
      if (point.patrimonio_melhor !== undefined && point.patrimonio_pior !== undefined) {
        row.melhor = point.patrimonio_melhor;
        row.pior = point.patrimonio_pior;
        row.faixaBase = point.patrimonio_pior;
        row.faixaAltura = point.patrimonio_melhor - point.patrimonio_pior;
      }
    }
    byDate.set(point.data, row);
  }
  const chartData = [...byDate.values()];

  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
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
        <Legend wrapperStyle={{ fontSize: 12, color: "var(--muted-foreground)" }} />
        <Area
          dataKey="faixaBase"
          stackId="faixa"
          stroke="none"
          fill="transparent"
          legendType="none"
          isAnimationActive={false}
        />
        <Area
          dataKey="faixaAltura"
          name="Faixa (melhor/pior mês recente)"
          stackId="faixa"
          stroke="none"
          fill="var(--chart-projecao)"
          fillOpacity={0.12}
          legendType="rect"
          isAnimationActive={false}
        />
        <Line
          type="monotone"
          dataKey="historico"
          name="Histórico"
          stroke="var(--chart-saldo)"
          strokeWidth={2}
          dot={{ r: 4, fill: "var(--chart-saldo)", stroke: "var(--card)", strokeWidth: 2 }}
          connectNulls={false}
          legendType="plainline"
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
          legendType="plainline"
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

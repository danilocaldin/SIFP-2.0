import { CategoryBarChart } from "@/components/charts/category-bar-chart";
import { MonthlyEvolutionChart } from "@/components/charts/monthly-evolution-chart";
import { MonthSelect } from "@/components/month-select";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getDashboard } from "@/lib/api";
import { formatBRL, formatPct, formatPctSigned } from "@/lib/format";

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ month?: string }>;
}) {
  const { month } = await searchParams;
  const dashboard = await getDashboard(month);

  if (!dashboard.has_data) {
    return (
      <main className="mx-auto flex min-h-[60vh] w-full max-w-4xl flex-col items-center justify-center gap-2 px-6 text-center">
        <h1 className="text-xl font-medium">Ainda não há dados importados</h1>
      </main>
    );
  }

  const monthLabels = Object.fromEntries(
    dashboard.monthly_evolution.map((m) => [m.month, m.mes_label])
  );

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-12 sm:py-16">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-muted-foreground">Dashboard</p>
          <h1 className="mt-1 text-xl font-semibold">Visão geral das finanças</h1>
        </div>
        <MonthSelect
          months={dashboard.months}
          selected={dashboard.selected_month}
          monthLabels={monthLabels}
        />
      </div>

      <p className="mt-6 text-base leading-relaxed">
        Em <span className="font-medium">{dashboard.period_label}</span>, você recebeu{" "}
        <span className="font-semibold">{formatBRL(dashboard.receitas)}</span>, gastou{" "}
        <span className="font-semibold">{formatBRL(dashboard.despesas)}</span> e{" "}
        {dashboard.saldo >= 0 ? (
          <>
            guardou <span className="font-semibold">{formatBRL(dashboard.saldo)}</span> — uma taxa
            de poupança de <span className="font-semibold">{formatPct(dashboard.taxa_poupanca_pct)}</span>{" "}
            da sua renda.
          </>
        ) : (
          <>
            ficou <span className="font-semibold text-red-500">{formatBRL(Math.abs(dashboard.saldo))} no vermelho</span>.
          </>
        )}
      </p>

      {dashboard.self_transfer_total > 0 && (
        <p className="mt-2 text-sm text-muted-foreground">
          ↔️ {formatBRL(dashboard.self_transfer_total)} foram movimentados entre suas próprias
          contas neste período — não contam como receita nem despesa acima.
        </p>
      )}

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Receitas" value={formatBRL(dashboard.receitas)} delta={dashboard.delta.receitas} />
        <StatCard
          label="Despesas"
          value={formatBRL(dashboard.despesas)}
          delta={dashboard.delta.despesas}
          invertDeltaColor
        />
        <StatCard label="Saldo" value={formatBRL(dashboard.saldo)} delta={dashboard.delta.saldo} />
      </div>

      <div className="mt-10 grid grid-cols-1 gap-8 lg:grid-cols-2">
        <div>
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">Gastos por categoria</h2>
          {dashboard.by_category.length > 0 ? (
            <CategoryBarChart data={dashboard.by_category} />
          ) : (
            <p className="text-sm text-muted-foreground">Sem despesas no período selecionado.</p>
          )}
        </div>
        <div>
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">
            Receita, despesa e saldo por mês
          </h2>
          <MonthlyEvolutionChart data={dashboard.monthly_evolution} />
        </div>
      </div>

      <div className="mt-10 grid grid-cols-1 gap-8 lg:grid-cols-2">
        <div>
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">
            Maiores gastos individuais do período
          </h2>
          {dashboard.top_expenses.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Data</TableHead>
                  <TableHead>Descrição</TableHead>
                  <TableHead className="text-right">Valor</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {dashboard.top_expenses.map((e) => (
                  <TableRow key={`${e.date}-${e.description}`}>
                    <TableCell className="text-muted-foreground">{e.date}</TableCell>
                    <TableCell>{e.description}</TableCell>
                    <TableCell className="text-right">{formatBRL(e.value_abs)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground">Sem despesas no período selecionado.</p>
          )}
        </div>
        <div>
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">
            Onde o dinheiro foi (por estabelecimento)
          </h2>
          {dashboard.top_merchants.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Estabelecimento</TableHead>
                  <TableHead className="text-right">Nº de compras</TableHead>
                  <TableHead className="text-right">Valor</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {dashboard.top_merchants.map((m) => (
                  <TableRow key={m.merchant}>
                    <TableCell>{m.merchant}</TableCell>
                    <TableCell className="text-right">{m.n_transacoes}</TableCell>
                    <TableCell className="text-right">{formatBRL(m.value_abs)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground">
              Sem dados de estabelecimento no período selecionado.
            </p>
          )}
        </div>
      </div>
    </main>
  );
}

function StatCard({
  label,
  value,
  delta,
  invertDeltaColor,
}: {
  label: string;
  value: string;
  delta: number | null;
  invertDeltaColor?: boolean;
}) {
  const positive = invertDeltaColor ? (delta ?? 0) <= 0 : (delta ?? 0) >= 0;
  return (
    <Card>
      <CardContent className="space-y-1">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-2xl font-semibold tracking-tight">{value}</p>
        {delta !== null && (
          <p className={`text-xs font-medium ${positive ? "text-emerald-600" : "text-red-500"}`}>
            {formatPctSigned(delta)} vs mês anterior
          </p>
        )}
      </CardContent>
    </Card>
  );
}

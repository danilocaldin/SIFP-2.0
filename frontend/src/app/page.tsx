import Link from "next/link";
import { MonthlyEvolutionChart } from "@/components/charts/monthly-evolution-chart";
import { DiagnosticCard } from "@/components/diagnostic-card";
import { NarrativaButton } from "@/components/narrativa-button";
import { Card, CardContent } from "@/components/ui/card";
import { getDashboard, getResumo } from "@/lib/api-server";
import { formatBRL, formatPct, formatPctSigned } from "@/lib/format";

export default async function Home() {
  const [resumo, dashboard] = await Promise.all([getResumo(), getDashboard()]);

  if (!resumo.has_data) {
    return (
      <main className="mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center gap-2 px-6 text-center">
        <h1 className="text-xl font-medium">Ainda não há dados importados</h1>
        <p className="text-sm text-muted-foreground">
          Importe um extrato para começar a ver como você está financeiramente.
        </p>
      </main>
    );
  }

  const topDiagnostic = resumo.diagnostics[0];
  const outrosDiagnosticos = resumo.diagnostics.length - 1;

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-12 sm:py-16">
      <p className="text-sm font-medium text-muted-foreground">Como você está agora</p>

      <div className="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="font-display text-5xl font-semibold tracking-tight text-foreground sm:text-6xl">
          {formatBRL(resumo.patrimonio_total)}
        </span>
        {resumo.delta_saldo_pct !== null && (
          <span
            className={`text-sm font-medium ${
              resumo.delta_saldo_pct >= 0 ? "text-emerald-600" : "text-red-500"
            }`}
          >
            {formatPctSigned(resumo.delta_saldo_pct)} de saldo vs mês anterior
          </span>
        )}
      </div>

      <div className="mt-3 max-w-2xl space-y-1 text-base leading-relaxed text-muted-foreground">
        <p>
          {resumo.taxa_mes_pct !== null && (
            <>
              Seus investimentos renderam{" "}
              <span className="font-medium text-foreground">{formatPct(resumo.taxa_mes_pct, 2)}</span>{" "}
              em {resumo.mes_label}
              {resumo.benchmark_mes_pct !== null && resumo.benchmark_nome && (
                <>
                  {" — "}
                  <span className="font-medium text-foreground">
                    {resumo.taxa_mes_pct >= resumo.benchmark_mes_pct ? "acima" : "abaixo"}
                  </span>{" "}
                  de {resumo.benchmark_nome} ({formatPct(resumo.benchmark_mes_pct, 2)})
                </>
              )}
              .
            </>
          )}
        </p>
        <p>
          {resumo.saldo >= 0 ? (
            <>
              Em {resumo.mes_label}, você guardou{" "}
              <span className="font-medium text-foreground">{formatPct(resumo.taxa_poupanca_pct)}</span>{" "}
              da renda ({formatBRL(resumo.saldo)}).
            </>
          ) : (
            <>
              Em {resumo.mes_label}, você fechou{" "}
              <span className="font-medium text-red-500">
                {formatBRL(Math.abs(resumo.saldo))} no vermelho
              </span>
              .
            </>
          )}
        </p>
      </div>

      <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Patrimônio total" value={formatBRL(resumo.patrimonio_total)} />
        <StatCard
          label={`Saldo em ${resumo.mes_label}`}
          value={formatBRL(resumo.saldo)}
          delta={resumo.delta_saldo_pct}
        />
        <StatCard label="Taxa de poupança" value={formatPct(resumo.taxa_poupanca_pct)} />
      </div>

      <div className="mt-10 grid grid-cols-1 gap-8 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-muted-foreground">Evolução mensal</h2>
            <Link
              href="/dashboard"
              className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
            >
              Ver dashboard completo
            </Link>
          </div>
          <Card className="mt-3">
            <CardContent>
              {dashboard.has_data && dashboard.monthly_evolution.length > 0 ? (
                <MonthlyEvolutionChart data={dashboard.monthly_evolution} />
              ) : (
                <p className="text-sm text-muted-foreground">Sem dados suficientes ainda.</p>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2">
          <h2 className="text-sm font-medium text-muted-foreground">O que mais importa agora</h2>

          <div className="mt-3">
            {!topDiagnostic ? (
              <Card>
                <CardContent>
                  <p className="text-sm">
                    ✅ Nada pedindo atenção agora — suas finanças estão dentro dos parâmetros que o
                    sistema verifica hoje.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-2">
                <DiagnosticCard diagnostic={topDiagnostic} />
                {outrosDiagnosticos > 0 && (
                  <p className="text-sm text-muted-foreground">
                    +{" "}
                    <Link
                      href="/diagnosticos"
                      className="underline underline-offset-2 hover:text-foreground"
                    >
                      {outrosDiagnosticos} outro(s) ponto(s) de atenção
                    </Link>
                    .
                  </p>
                )}
              </div>
            )}
          </div>

          <p className="mt-4 text-sm text-muted-foreground">
            {resumo.saldo_medio_3m > 0 && resumo.projecao_12m !== null ? (
              <>
                📈 No ritmo atual, seu patrimônio deve chegar perto de{" "}
                <span className="font-medium text-foreground">{formatBRL(resumo.projecao_12m)}</span>{" "}
                em 12 meses.
              </>
            ) : (
              <>
                📉 Nos últimos 3 meses seu saldo médio foi negativo — no ritmo atual, seu patrimônio
                não cresce.
              </>
            )}
          </p>
        </div>
      </div>

      <NarrativaButton />
    </main>
  );
}

function StatCard({
  label,
  value,
  delta,
}: {
  label: string;
  value: string;
  delta?: number | null;
}) {
  return (
    <Card>
      <CardContent className="space-y-1">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-2xl font-semibold tracking-tight">{value}</p>
        {delta !== undefined && delta !== null && (
          <p
            className={`text-xs font-medium ${
              delta >= 0 ? "text-emerald-600" : "text-red-500"
            }`}
          >
            {formatPctSigned(delta)} vs mês anterior
          </p>
        )}
      </CardContent>
    </Card>
  );
}

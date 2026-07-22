import Link from "next/link";
import { DiagnosticCard } from "@/components/diagnostic-card";
import { NarrativaButton } from "@/components/narrativa-button";
import { Card, CardContent } from "@/components/ui/card";
import { getResumo } from "@/lib/api";
import { formatBRL, formatPct, formatPctSigned } from "@/lib/format";

export default async function Home() {
  const resumo = await getResumo();

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
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-12 sm:py-16">
      <p className="text-sm font-medium text-muted-foreground">
        Como você está agora
      </p>

      <div className="mt-3 space-y-1 text-lg leading-relaxed sm:text-xl">
        <p>
          Seu patrimônio é{" "}
          <span className="font-semibold">
            {formatBRL(resumo.patrimonio_total)}
          </span>
          .{" "}
          {resumo.taxa_mes_pct !== null && (
            <>
              Seus investimentos renderam{" "}
              <span className="font-semibold">
                {formatPct(resumo.taxa_mes_pct, 2)}
              </span>{" "}
              em {resumo.mes_label}
              {resumo.benchmark_mes_pct !== null && resumo.benchmark_nome && (
                <>
                  {" — "}
                  <span className="font-semibold">
                    {resumo.taxa_mes_pct >= resumo.benchmark_mes_pct
                      ? "acima"
                      : "abaixo"}
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
              <span className="font-semibold">
                {formatPct(resumo.taxa_poupanca_pct)}
              </span>{" "}
              da renda ({formatBRL(resumo.saldo)}).
            </>
          ) : (
            <>
              Em {resumo.mes_label}, você fechou{" "}
              <span className="font-semibold text-red-500">
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

      <div className="mt-10">
        <h2 className="mb-3 text-sm font-medium text-muted-foreground">
          O que mais importa agora
        </h2>

        {!topDiagnostic ? (
          <Card>
            <CardContent>
              <p className="text-sm">
                ✅ Nada pedindo atenção agora — suas finanças estão dentro dos
                parâmetros que o sistema verifica hoje.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-2">
            <DiagnosticCard diagnostic={topDiagnostic} />
            {outrosDiagnosticos > 0 && (
              <p className="text-sm text-muted-foreground">
                +{" "}
                <Link href="/diagnosticos" className="underline underline-offset-2 hover:text-foreground">
                  {outrosDiagnosticos} outro(s) ponto(s) de atenção
                </Link>
                .
              </p>
            )}
          </div>
        )}
      </div>

      <p className="mt-8 text-sm text-muted-foreground">
        {resumo.saldo_medio_3m > 0 && resumo.projecao_12m !== null ? (
          <>
            📈 No ritmo atual, seu patrimônio deve chegar perto de{" "}
            <span className="font-medium text-foreground">
              {formatBRL(resumo.projecao_12m)}
            </span>{" "}
            em 12 meses.
          </>
        ) : (
          <>
            📉 Nos últimos 3 meses seu saldo médio foi negativo — no ritmo
            atual, seu patrimônio não cresce.
          </>
        )}
      </p>

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

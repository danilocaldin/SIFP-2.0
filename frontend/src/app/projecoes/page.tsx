import { ProjectionChart } from "@/components/charts/projection-chart";
import { HorizonteSelect } from "@/components/horizonte-select";
import { Card, CardContent } from "@/components/ui/card";
import { getProjecoes } from "@/lib/api";
import { formatBRL, formatPct } from "@/lib/format";

const VALID_HORIZONTES = [6, 12, 24];

export default async function ProjecoesPage({
  searchParams,
}: {
  searchParams: Promise<{ horizonte?: string }>;
}) {
  const { horizonte: horizonteParam } = await searchParams;
  const horizonte = VALID_HORIZONTES.includes(Number(horizonteParam)) ? Number(horizonteParam) : 12;
  const projecoes = await getProjecoes(horizonte);

  if (!projecoes.has_data) {
    return (
      <main className="mx-auto flex min-h-[60vh] w-full max-w-3xl flex-col items-center justify-center gap-2 px-6 text-center">
        <h1 className="text-xl font-medium">Ainda não há dados importados</h1>
      </main>
    );
  }

  const semSaldo = projecoes.saldo_medio_3m <= 0;

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-12 sm:py-16">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-muted-foreground">Projeções</p>
          <h1 className="mt-1 text-xl font-semibold">
            Se o ritmo atual continuar, é pra onde você está indo
          </h1>
        </div>
        <HorizonteSelect horizonte={horizonte} />
      </div>
      <p className="mt-2 text-sm text-muted-foreground">
        Não é uma previsão do futuro — é o que aconteceria se nada mudasse.
      </p>

      {semSaldo ? (
        <Card className="mt-6 border-l-4 border-l-orange-500">
          <CardContent>
            <p className="text-sm">
              Nos últimos meses seu saldo médio foi{" "}
              <span className="font-medium">{formatBRL(projecoes.saldo_medio_3m)}/mês</span> — no
              ritmo atual, seu patrimônio não cresce. Ajustar isso é o primeiro passo antes de
              projetar crescimento.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <p className="mt-6 text-base leading-relaxed">
            No ritmo médio dos últimos 3 meses (
            <span className="font-semibold">{formatBRL(projecoes.saldo_medio_3m)}/mês</span>{" "}
            guardados)
            {projecoes.taxa_rentabilidade_12m !== null && (
              <>
                , considerando também que seus investimentos atuais rendem em média{" "}
                <span className="font-semibold">
                  {formatPct(projecoes.taxa_rentabilidade_12m, 2)} a.a.
                </span>
              </>
            )}
            , seu patrimônio deve ir de{" "}
            <span className="font-semibold">{formatBRL(projecoes.patrimonio_atual)}</span> para{" "}
            <span className="font-semibold">{formatBRL(projecoes.patrimonio_final ?? 0)}</span> em{" "}
            {horizonte} meses.
          </p>

          <div className="mt-6">
            {projecoes.chart.length > 0 ? (
              <ProjectionChart data={projecoes.chart} />
            ) : (
              <p className="text-sm text-muted-foreground">
                Sem histórico de patrimônio suficiente pra desenhar o gráfico.
              </p>
            )}
          </div>
        </>
      )}

      <div className="mt-10">
        <h2 className="mb-3 text-sm font-medium text-muted-foreground">Suas metas nesse ritmo</h2>

        {projecoes.goals.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhuma meta cadastrada — defina uma na aba Orçamento e Metas.
          </p>
        ) : (
          <div className="space-y-2">
            {projecoes.goals.map((goal) => (
              <GoalCard key={goal.id} goal={goal} />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

function GoalCard({
  goal,
}: {
  goal: {
    nome: string;
    eta_meses: number | null;
    data_prevista: string | null;
    dentro_do_prazo: boolean | null;
    prazo: string;
    valor_necessario: number;
    valor_acumulado: number;
  };
}) {
  if (goal.eta_meses === 0) {
    return (
      <Card className="border-l-4 border-l-emerald-500">
        <CardContent>
          <p className="text-sm">
            ✅ <span className="font-medium">{goal.nome}</span> já está concluída.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (goal.eta_meses === null) {
    const faltante = goal.valor_necessario - goal.valor_acumulado;
    return (
      <Card className="border-l-4 border-l-red-500">
        <CardContent>
          <p className="text-sm">
            🔴 <span className="font-medium">{goal.nome}</span> — no ritmo atual de poupança, essa
            meta não é atingida (faltam {formatBRL(faltante)} e o saldo médio recente é zero ou
            negativo).
          </p>
        </CardContent>
      </Card>
    );
  }

  const dentro = goal.dentro_do_prazo;
  return (
    <Card className={`border-l-4 ${dentro ? "border-l-blue-500" : "border-l-orange-500"}`}>
      <CardContent>
        <p className="text-sm">
          {dentro ? "🔵" : "🟠"} <span className="font-medium">{goal.nome}</span> — no ritmo atual,
          atingida em ~{goal.eta_meses} mês(es) (por volta de {goal.data_prevista}),{" "}
          {dentro ? "antes" : "depois"} do prazo definido ({goal.prazo}).
        </p>
      </CardContent>
    </Card>
  );
}

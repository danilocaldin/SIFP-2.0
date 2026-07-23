import { ReportActions } from "@/components/report-actions";
import { ReportMonthSelect } from "@/components/report-month-select";
import { getRelatorio } from "@/lib/api-server";

export default async function RelatorioPage({
  searchParams,
}: {
  searchParams: Promise<{ month?: string }>;
}) {
  const { month } = await searchParams;
  const relatorio = await getRelatorio(month);

  if (!relatorio.has_data) {
    return (
      <main className="mx-auto flex min-h-[60vh] w-full max-w-4xl flex-col items-center justify-center gap-2 px-6 text-center">
        <h1 className="text-xl font-medium">Ainda não há dados importados</h1>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-12 sm:py-16">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-muted-foreground">Relatório</p>
          <h1 className="mt-1 text-xl font-semibold">Relatório financeiro</h1>
        </div>
        <ReportMonthSelect
          months={relatorio.months}
          selected={relatorio.selected_month}
          monthLabels={relatorio.months_labels}
        />
      </div>

      <p className="mt-2 text-sm text-muted-foreground">
        Consolida em um único texto o que as outras telas já mostram — resumo, categorias,
        estabelecimentos, diagnósticos, patrimônio e dívidas — pronto pra copiar, salvar ou
        compartilhar.
      </p>

      <div className="mt-6 flex items-center justify-between gap-4">
        <p className="text-sm font-medium">{relatorio.period_label}</p>
        <ReportActions reportText={relatorio.report_text} month={relatorio.selected_month} />
      </div>

      <pre className="mt-4 max-h-[600px] overflow-auto rounded-lg border border-border bg-muted/40 p-4 font-mono text-xs leading-relaxed whitespace-pre-wrap">
        {relatorio.report_text}
      </pre>
    </main>
  );
}

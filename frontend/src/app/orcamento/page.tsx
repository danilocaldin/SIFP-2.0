import { BudgetSection } from "@/components/budget-section";
import { GoalsSection } from "@/components/goals-section";
import { getMetas, getOrcamento } from "@/lib/api";

export default async function OrcamentoPage() {
  const [orcamento, metas] = await Promise.all([getOrcamento(), getMetas()]);

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-12 sm:py-16">
      <p className="text-sm font-medium text-muted-foreground">Orçamento e Metas</p>
      <h1 className="mt-1 text-xl font-semibold">Limites e metas financeiras</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Defina limites de gasto por categoria e metas financeiras — os alertas da aba Diagnósticos
        e o Relatório passam a considerá-los automaticamente assim que você cadastrar algum.
      </p>

      <div className="mt-8 grid grid-cols-1 gap-10 lg:grid-cols-2">
        <BudgetSection data={orcamento} />
        <GoalsSection goals={metas} />
      </div>
    </main>
  );
}

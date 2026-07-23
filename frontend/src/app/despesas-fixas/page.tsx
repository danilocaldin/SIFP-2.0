import { DespesasFixasSection } from "@/components/despesas-fixas-section";
import { getDespesasFixas } from "@/lib/api-server";

export default async function DespesasFixasPage() {
  const data = await getDespesasFixas();

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-12 sm:py-16">
      <p className="text-sm font-medium text-muted-foreground">Despesas Fixas</p>
      <h1 className="mt-1 text-xl font-semibold">Compromissos recorrentes</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Declare seus compromissos recorrentes — assinatura, plano de saúde, psicóloga, compra
        parcelada — pra ver quanto já está comprometido todo mês e decidir com mais segurança se
        cabe assumir mais uma dívida.
      </p>

      <div className="mt-8">
        <DespesasFixasSection data={data} />
      </div>
    </main>
  );
}

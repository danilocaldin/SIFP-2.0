import { RevisaoLote } from "@/components/revisao-lote";
import { RevisaoTable } from "@/components/revisao-table";
import { getRevisao } from "@/lib/api";

export default async function RevisaoPage() {
  const revisao = await getRevisao();

  if (!revisao.has_data) {
    return (
      <main className="mx-auto flex min-h-[60vh] w-full max-w-4xl flex-col items-center justify-center gap-2 px-6 text-center">
        <h1 className="text-xl font-medium">Ainda não há dados importados</h1>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-12 sm:py-16">
      <p className="text-sm font-medium text-muted-foreground">Revisão de Categorias</p>
      <h1 className="mt-1 text-xl font-semibold">Revise e corrija as categorias sugeridas</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        O que você salvar aqui vira memória permanente por descrição: uma descrição que você
        sempre classifica igual (ex: um mercado, um app de transporte) passa a ser categorizada
        sozinha nas próximas importações. Uma descrição que já variou entre categorias diferentes
        (ex: um Pix para a mesma pessoa que às vezes é uma coisa, às vezes é outra) o sistema
        deixa sempre marcada como &quot;{revisao.categoria_nao_categorizada}&quot;, porque sabe
        que precisa da sua decisão a cada vez.
      </p>

      <div className="mt-8 space-y-8">
        <RevisaoLote pendentes={revisao.lote_pendentes} categorias={revisao.categorias} />
        <RevisaoTable
          transactions={revisao.transactions}
          categorias={revisao.categorias}
          categoriaNaoCategorizada={revisao.categoria_nao_categorizada}
        />
      </div>
    </main>
  );
}

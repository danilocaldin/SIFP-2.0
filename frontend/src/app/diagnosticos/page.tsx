import { DiagnosticCard } from "@/components/diagnostic-card";
import { getResumo } from "@/lib/api-server";

export default async function DiagnosticosPage() {
  const resumo = await getResumo();

  if (!resumo.has_data) {
    return (
      <main className="mx-auto flex min-h-[60vh] w-full max-w-3xl flex-col items-center justify-center gap-2 px-6 text-center">
        <h1 className="text-xl font-medium">Ainda não há dados importados</h1>
      </main>
    );
  }

  const { diagnostics } = resumo;
  const nCritica = diagnostics.filter((d) => d.severidade === "critica").length;
  const nAlta = diagnostics.filter((d) => d.severidade === "alta").length;

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-12 sm:py-16">
      <p className="text-sm font-medium text-muted-foreground">Diagnósticos automáticos</p>
      <h1 className="mt-1 text-xl font-semibold">
        Leituras sobre suas finanças, não só os números
      </h1>

      <p className="mt-6 text-base">
        {diagnostics.length === 0 ? (
          "✅ Nenhum diagnóstico no momento — suas finanças estão dentro dos parâmetros que o sistema verifica hoje."
        ) : nCritica > 0 ? (
          <>
            🔴 {diagnostics.length} ponto{diagnostics.length !== 1 ? "s" : ""} de atenção agora —{" "}
            {nCritica} crítico(s), comece por eles.
          </>
        ) : nAlta > 0 ? (
          <>
            🟠 {diagnostics.length} ponto{diagnostics.length !== 1 ? "s" : ""} de atenção agora —
            nada crítico, mas vale olhar.
          </>
        ) : (
          <>
            🔵 {diagnostics.length} ponto{diagnostics.length !== 1 ? "s" : ""} de atenção agora —
            nada urgente.
          </>
        )}
      </p>

      <div className="mt-6 space-y-3">
        {diagnostics.map((d) => (
          <DiagnosticCard key={d.codigo} diagnostic={d} />
        ))}
      </div>
    </main>
  );
}

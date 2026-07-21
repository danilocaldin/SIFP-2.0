import { Card, CardContent } from "@/components/ui/card";
import { formatBRL } from "@/lib/format";
import type { Diagnostic, Severidade } from "@/lib/types";

// Mesma paleta semântica do app Streamlit (SEVERITY_ICON/SEVERITY_RENDER):
// crítica=vermelho, alta=laranja, média=amarelo, baixa=azul. Cor sempre
// significa a mesma coisa em qualquer tela do SIFP.
const SEVERITY_STYLE: Record<
  Severidade,
  { border: string; dot: string; label: string }
> = {
  critica: { border: "border-l-red-500", dot: "bg-red-500", label: "Crítico" },
  alta: { border: "border-l-orange-500", dot: "bg-orange-500", label: "Alto" },
  media: { border: "border-l-amber-400", dot: "bg-amber-400", label: "Médio" },
  baixa: { border: "border-l-blue-500", dot: "bg-blue-500", label: "Baixo" },
};

export function DiagnosticCard({ diagnostic }: { diagnostic: Diagnostic }) {
  const style = SEVERITY_STYLE[diagnostic.severidade];

  return (
    <Card className={`border-l-4 ${style.border}`}>
      <CardContent className="space-y-2">
        <div className="flex items-center gap-2">
          <span className={`inline-block h-2 w-2 rounded-full ${style.dot}`} />
          <h3 className="font-medium leading-snug">{diagnostic.titulo}</h3>
        </div>
        <p className="text-sm text-muted-foreground">{diagnostic.descricao}</p>
        <p className="text-sm">
          <span className="font-medium">Recomendação: </span>
          {diagnostic.recomendacao}
        </p>
        {diagnostic.impacto_financeiro !== null && (
          <p className="text-sm font-medium">
            Impacto: {formatBRL(Math.abs(diagnostic.impacto_financeiro))}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

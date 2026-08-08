import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { formatBRL } from "@/lib/format";
import type { Diagnostic, Severidade } from "@/lib/types";

// Mesma paleta semântica do app Streamlit (SEVERITY_ICON/SEVERITY_RENDER):
// crítica=vermelho, alta=laranja, média=amarelo, baixa=azul. Cor sempre
// significa a mesma coisa em qualquer tela do SIFP. A severidade também
// precisa ficar legível como texto (badge), não só pela cor — daltonismo
// e telas em preto-e-branco não distinguem vermelho de laranja.
const SEVERITY_STYLE: Record<
  Severidade,
  { border: string; dot: string; badge: string; label: string }
> = {
  critica: {
    border: "border-l-red-500",
    dot: "bg-red-500",
    badge: "border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400",
    label: "Crítico",
  },
  alta: {
    border: "border-l-orange-500",
    dot: "bg-orange-500",
    badge: "border-orange-500/30 bg-orange-500/10 text-orange-600 dark:text-orange-400",
    label: "Alto",
  },
  media: {
    border: "border-l-amber-400",
    dot: "bg-amber-400",
    badge: "border-amber-400/30 bg-amber-400/10 text-amber-600 dark:text-amber-400",
    label: "Médio",
  },
  baixa: {
    border: "border-l-blue-500",
    dot: "bg-blue-500",
    badge: "border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400",
    label: "Baixo",
  },
};

export function DiagnosticCard({ diagnostic }: { diagnostic: Diagnostic }) {
  const style = SEVERITY_STYLE[diagnostic.severidade];

  return (
    <Card className={`border-l-4 ${style.border}`}>
      <CardContent className="space-y-2">
        <div className="flex items-center gap-2">
          <span className={`inline-block h-2 w-2 rounded-full ${style.dot}`} />
          <h3 className="font-medium leading-snug">{diagnostic.titulo}</h3>
          <Badge variant="outline" className={style.badge}>
            {style.label}
          </Badge>
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

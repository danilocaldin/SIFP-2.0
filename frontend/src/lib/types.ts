// Espelha o payload de GET /api/resumo (sifp/services/summary_service.py).
// Mantido em sincronia manualmente por enquanto — sem gerador de tipos
// ainda, o payload é pequeno e estável.

export type Severidade = "critica" | "alta" | "media" | "baixa";

export interface Diagnostic {
  codigo: string;
  titulo: string;
  severidade: Severidade;
  descricao: string;
  explicacao: string;
  recomendacao: string;
  impacto_financeiro: number | null;
  prioridade: number;
}

export interface ResumoData {
  has_data: true;
  mes: string;
  mes_label: string;
  patrimonio_total: number;
  taxa_mes_pct: number | null;
  benchmark_mes_pct: number | null;
  benchmark_nome: string | null;
  saldo: number;
  taxa_poupanca_pct: number;
  delta_saldo_pct: number | null;
  saldo_medio_3m: number;
  projecao_12m: number | null;
  diagnostics: Diagnostic[];
}

export interface ResumoEmpty {
  has_data: false;
}

export type Resumo = ResumoData | ResumoEmpty;

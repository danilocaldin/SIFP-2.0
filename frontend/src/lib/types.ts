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

// Espelha GET /api/dashboard (sifp/services/dashboard_service.py).

export interface CategoryBreakdown {
  category: string;
  value_abs: number;
  pct: number;
}

export interface MonthlyEvolution {
  month: string;
  mes_label: string;
  Receitas: number;
  Despesas: number;
  Saldo: number;
}

export interface TopExpense {
  date: string;
  description: string;
  category: string;
  value_abs: number;
}

export interface TopMerchant {
  merchant: string;
  value_abs: number;
  n_transacoes: number;
}

export interface DashboardData {
  has_data: true;
  months: string[];
  selected_month: string | null;
  period_label: string;
  receitas: number;
  despesas: number;
  saldo: number;
  taxa_poupanca_pct: number;
  delta: { receitas: number | null; despesas: number | null; saldo: number | null };
  self_transfer_total: number;
  by_category: CategoryBreakdown[];
  monthly_evolution: MonthlyEvolution[];
  top_expenses: TopExpense[];
  top_merchants: TopMerchant[];
}

export interface DashboardEmpty {
  has_data: false;
}

export type Dashboard = DashboardData | DashboardEmpty;

// Espelha GET /api/patrimonio (sifp/services/patrimonio_service.py).

export interface AssetPosition {
  nome: string;
  tipo: string;
  instituicao: string;
  data_referencia: string;
  saldo_liquido: number;
  rentabilidade_12m_pct: number | null;
  benchmark: string | null;
  benchmark_12m_pct: number | null;
}

export interface NetWorthPoint {
  data_referencia: string;
  patrimonio_total: number;
}

export interface PatrimonioData {
  has_data: true;
  patrimonio_total: number;
  assets: AssetPosition[];
  net_worth_history: NetWorthPoint[];
}

export interface PatrimonioEmpty {
  has_data: false;
}

export type Patrimonio = PatrimonioData | PatrimonioEmpty;

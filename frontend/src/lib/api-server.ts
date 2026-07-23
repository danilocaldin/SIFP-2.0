import type {
  Dashboard,
  DespesasFixasData,
  Goal,
  OrcamentoData,
  Patrimonio,
  Projecoes,
  Relatorio,
  Resumo,
  Revisao,
} from "@/lib/types";
import { API_PREFIX, SAAS_MODE } from "@/lib/api";
import { createClient as createServerSupabaseClient } from "@/lib/supabase/server";

// Buscas (GET) usadas só por Server Components — separado de api.ts de
// propósito, porque este arquivo importa @/lib/supabase/server (que usa
// next/headers, proibido em Client Components). Ver api.ts pro resto
// (mutações, chamadas do navegador).

// Server Components rodam no processo Node do Next, então este fetch é
// servidor-para-servidor — nunca passa pelo navegador, não precisa de CORS.
const API_URL = process.env.SIFP_API_URL ?? "http://localhost:8000";

async function authHeadersServer(): Promise<Record<string, string>> {
  if (!SAAS_MODE) return {};
  const supabase = await createServerSupabaseClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session ? { Authorization: `Bearer ${session.access_token}` } : {};
}

export async function getResumo(): Promise<Resumo> {
  const res = await fetch(`${API_URL}${API_PREFIX}/resumo`, {
    cache: "no-store",
    headers: await authHeadersServer(),
  });
  if (!res.ok) {
    throw new Error(`Falha ao buscar ${API_PREFIX}/resumo: ${res.status}`);
  }
  return res.json();
}

export async function getDashboard(month?: string): Promise<Dashboard> {
  const url = new URL(`${API_URL}${API_PREFIX}/dashboard`);
  if (month) url.searchParams.set("month", month);
  const res = await fetch(url, { cache: "no-store", headers: await authHeadersServer() });
  if (!res.ok) {
    throw new Error(`Falha ao buscar ${API_PREFIX}/dashboard: ${res.status}`);
  }
  return res.json();
}

export async function getPatrimonio(): Promise<Patrimonio> {
  const res = await fetch(`${API_URL}${API_PREFIX}/patrimonio`, {
    cache: "no-store",
    headers: await authHeadersServer(),
  });
  if (!res.ok) {
    throw new Error(`Falha ao buscar ${API_PREFIX}/patrimonio: ${res.status}`);
  }
  return res.json();
}

export async function getProjecoes(horizonte: number = 12): Promise<Projecoes> {
  const url = new URL(`${API_URL}${API_PREFIX}/projecoes`);
  url.searchParams.set("horizonte", String(horizonte));
  const res = await fetch(url, { cache: "no-store", headers: await authHeadersServer() });
  if (!res.ok) {
    throw new Error(`Falha ao buscar ${API_PREFIX}/projecoes: ${res.status}`);
  }
  return res.json();
}

export async function getOrcamento(): Promise<OrcamentoData> {
  const res = await fetch(`${API_URL}${API_PREFIX}/orcamento`, {
    cache: "no-store",
    headers: await authHeadersServer(),
  });
  if (!res.ok) {
    throw new Error(`Falha ao buscar ${API_PREFIX}/orcamento: ${res.status}`);
  }
  return res.json();
}

export async function getMetas(): Promise<Goal[]> {
  const res = await fetch(`${API_URL}${API_PREFIX}/metas`, {
    cache: "no-store",
    headers: await authHeadersServer(),
  });
  if (!res.ok) {
    throw new Error(`Falha ao buscar ${API_PREFIX}/metas: ${res.status}`);
  }
  return res.json();
}

export async function getDespesasFixas(): Promise<DespesasFixasData> {
  const res = await fetch(`${API_URL}${API_PREFIX}/despesas-fixas`, {
    cache: "no-store",
    headers: await authHeadersServer(),
  });
  if (!res.ok) {
    throw new Error(`Falha ao buscar ${API_PREFIX}/despesas-fixas: ${res.status}`);
  }
  return res.json();
}

export async function getRevisao(): Promise<Revisao> {
  const res = await fetch(`${API_URL}${API_PREFIX}/revisao`, {
    cache: "no-store",
    headers: await authHeadersServer(),
  });
  if (!res.ok) {
    throw new Error(`Falha ao buscar ${API_PREFIX}/revisao: ${res.status}`);
  }
  return res.json();
}

export async function getRelatorio(month?: string): Promise<Relatorio> {
  const url = new URL(`${API_URL}${API_PREFIX}/relatorio`);
  if (month) url.searchParams.set("month", month);
  const res = await fetch(url, { cache: "no-store", headers: await authHeadersServer() });
  if (!res.ok) {
    throw new Error(`Falha ao buscar ${API_PREFIX}/relatorio: ${res.status}`);
  }
  return res.json();
}

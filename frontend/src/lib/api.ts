import type { Dashboard, Patrimonio, Projecoes, Resumo } from "@/lib/types";

// Server Components rodam no processo Node do Next, então este fetch é
// servidor-para-servidor — nunca passa pelo navegador, não precisa de CORS.
const API_URL = process.env.SIFP_API_URL ?? "http://localhost:8000";

// Client Components (ex: upload de PDF) chamam a API direto do navegador —
// precisa do prefixo NEXT_PUBLIC_ pro Next.js embutir o valor no bundle do
// cliente (a variável sem prefixo só existe no lado servidor). Nesse
// caminho o CORS do backend entra em ação (ver sifp/api/main.py).
export const PUBLIC_API_URL = process.env.NEXT_PUBLIC_SIFP_API_URL ?? "http://localhost:8000";

export async function getResumo(): Promise<Resumo> {
  const res = await fetch(`${API_URL}/api/resumo`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Falha ao buscar /api/resumo: ${res.status}`);
  }
  return res.json();
}

export async function getDashboard(month?: string): Promise<Dashboard> {
  const url = new URL(`${API_URL}/api/dashboard`);
  if (month) url.searchParams.set("month", month);
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Falha ao buscar /api/dashboard: ${res.status}`);
  }
  return res.json();
}

export async function getPatrimonio(): Promise<Patrimonio> {
  const res = await fetch(`${API_URL}/api/patrimonio`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Falha ao buscar /api/patrimonio: ${res.status}`);
  }
  return res.json();
}

export async function getProjecoes(horizonte: number = 12): Promise<Projecoes> {
  const url = new URL(`${API_URL}/api/projecoes`);
  url.searchParams.set("horizonte", String(horizonte));
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Falha ao buscar /api/projecoes: ${res.status}`);
  }
  return res.json();
}

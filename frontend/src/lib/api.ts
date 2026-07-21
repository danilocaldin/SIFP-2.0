import type { Resumo } from "@/lib/types";

// Server Components rodam no processo Node do Next, então este fetch é
// servidor-para-servidor — nunca passa pelo navegador, não precisa de CORS.
const API_URL = process.env.SIFP_API_URL ?? "http://localhost:8000";

export async function getResumo(): Promise<Resumo> {
  const res = await fetch(`${API_URL}/api/resumo`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Falha ao buscar /api/resumo: ${res.status}`);
  }
  return res.json();
}

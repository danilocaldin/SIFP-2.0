import type {
  Dashboard,
  Goal,
  OrcamentoData,
  Patrimonio,
  Projecoes,
  Relatorio,
  Resumo,
  Revisao,
  UploadPersistSummary,
  UploadPreview,
} from "@/lib/types";

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

export async function getOrcamento(): Promise<OrcamentoData> {
  const res = await fetch(`${API_URL}/api/orcamento`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Falha ao buscar /api/orcamento: ${res.status}`);
  }
  return res.json();
}

export async function getMetas(): Promise<Goal[]> {
  const res = await fetch(`${API_URL}/api/metas`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Falha ao buscar /api/metas: ${res.status}`);
  }
  return res.json();
}

export async function getRevisao(): Promise<Revisao> {
  const res = await fetch(`${API_URL}/api/revisao`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Falha ao buscar /api/revisao: ${res.status}`);
  }
  return res.json();
}

export async function getRelatorio(month?: string): Promise<Relatorio> {
  const url = new URL(`${API_URL}/api/relatorio`);
  if (month) url.searchParams.set("month", month);
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Falha ao buscar /api/relatorio: ${res.status}`);
  }
  return res.json();
}

// --- Mutações: chamadas do navegador (Client Components), usam PUBLIC_API_URL ---

async function parseErrorDetail(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    return body.detail ?? fallback;
  } catch {
    return fallback;
  }
}

export async function criarLimite(category: string, valor: number): Promise<void> {
  const res = await fetch(`${PUBLIC_API_URL}/api/orcamento/limites`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category, valor }),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao salvar o limite."));
}

export async function removerLimite(category: string): Promise<void> {
  const res = await fetch(`${PUBLIC_API_URL}/api/orcamento/limites/${encodeURIComponent(category)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao remover o limite."));
}

export async function criarMeta(nome: string, valorNecessario: number, prazo: string): Promise<void> {
  const res = await fetch(`${PUBLIC_API_URL}/api/metas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nome, valor_necessario: valorNecessario, prazo }),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao criar a meta."));
}

export async function atualizarProgressoMeta(id: number, valorAcumulado: number): Promise<void> {
  const res = await fetch(`${PUBLIC_API_URL}/api/metas/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ valor_acumulado: valorAcumulado }),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao atualizar a meta."));
}

export async function excluirMeta(id: number): Promise<void> {
  const res = await fetch(`${PUBLIC_API_URL}/api/metas/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao excluir a meta."));
}

export async function previewUpload(file: File): Promise<UploadPreview> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${PUBLIC_API_URL}/api/upload/preview`, { method: "POST", body: formData });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao ler o arquivo."));
  return res.json();
}

export async function persistUpload(file: File): Promise<UploadPersistSummary> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${PUBLIC_API_URL}/api/upload/persist`, { method: "POST", body: formData });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao importar o arquivo."));
  return res.json();
}

export async function aplicarCategoriaEmLote(
  description: string,
  category: string
): Promise<{ atualizadas: number; mensagem_treino: string }> {
  const res = await fetch(`${PUBLIC_API_URL}/api/revisao/lote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description, category }),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao aplicar categoria em lote."));
  return res.json();
}

export async function confirmarRevisao(
  updates: { tx_hash: string; category: string }[]
): Promise<{ confirmadas: number; ainda_pendentes: number; mensagem_treino: string }> {
  const res = await fetch(`${PUBLIC_API_URL}/api/revisao/confirmar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ updates }),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao confirmar a revisão."));
  return res.json();
}

export async function retreinarModelo(): Promise<{ mensagem: string }> {
  const res = await fetch(`${PUBLIC_API_URL}/api/revisao/retreinar`, { method: "POST" });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao re-treinar o modelo."));
  return res.json();
}

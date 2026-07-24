import type {
  ChatMensagem,
  ChatResponse,
  NarrativaResponse,
  TipoDespesaFixa,
  UploadPersistSummary,
  UploadPreview,
} from "@/lib/types";
import { createClient as createBrowserSupabaseClient } from "@/lib/supabase/client";

// Este arquivo é seguro pra importar de Client Components — nunca toca
// next/headers nem nada exclusivo de servidor. As buscas (get*) usadas por
// Server Components ficam em api-server.ts, separado de propósito: um
// import estático de next/headers aqui quebraria qualquer Client
// Component que importasse deste mesmo módulo (ver narrativa-button.tsx).

// Client Components (ex: upload de PDF) chamam a API direto do navegador —
// precisa do prefixo NEXT_PUBLIC_ pro Next.js embutir o valor no bundle do
// cliente (a variável sem prefixo só existe no lado servidor). Nesse
// caminho o CORS do backend entra em ação (ver sifp/api/main.py).
export const PUBLIC_API_URL = process.env.NEXT_PUBLIC_SIFP_API_URL ?? "http://localhost:8000";

// Mesmo código-fonte, dois deploys: o Sifra pessoal do Danilo (sem login,
// SQLite, rotas /api/...) e o SaaS multiusuário (login obrigatório,
// Postgres+RLS, rotas /api/v2/...). SAAS_MODE=true muda o prefixo das
// rotas e passa a anexar o token de sessão do Supabase em toda chamada —
// nada mais muda (mesmas telas, mesmos componentes).
export const SAAS_MODE = process.env.NEXT_PUBLIC_SAAS_MODE === "true";
export const API_PREFIX = SAAS_MODE ? "/api/v2" : "/api";

async function authHeadersClient(): Promise<Record<string, string>> {
  if (!SAAS_MODE) return {};
  const supabase = createBrowserSupabaseClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session ? { Authorization: `Bearer ${session.access_token}` } : {};
}

async function parseErrorDetail(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    return body.detail ?? fallback;
  } catch {
    return fallback;
  }
}

export async function getEmailImportacao(): Promise<{ email: string } | null> {
  const res = await fetch(`${PUBLIC_API_URL}${API_PREFIX}/perfil/email-importacao`, {
    headers: await authHeadersClient(),
  });
  if (!res.ok) return null;
  return res.json();
}

export async function criarLimite(category: string, valor: number): Promise<void> {
  const res = await fetch(`${PUBLIC_API_URL}${API_PREFIX}/orcamento/limites`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeadersClient()) },
    body: JSON.stringify({ category, valor }),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao salvar o limite."));
}

export async function removerLimite(category: string): Promise<void> {
  const res = await fetch(`${PUBLIC_API_URL}${API_PREFIX}/orcamento/limites/${encodeURIComponent(category)}`, {
    method: "DELETE",
    headers: await authHeadersClient(),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao remover o limite."));
}

export async function criarMeta(nome: string, valorNecessario: number, prazo: string): Promise<void> {
  const res = await fetch(`${PUBLIC_API_URL}${API_PREFIX}/metas`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeadersClient()) },
    body: JSON.stringify({ nome, valor_necessario: valorNecessario, prazo }),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao criar a meta."));
}

export async function atualizarProgressoMeta(id: number, valorAcumulado: number): Promise<void> {
  const res = await fetch(`${PUBLIC_API_URL}${API_PREFIX}/metas/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...(await authHeadersClient()) },
    body: JSON.stringify({ valor_acumulado: valorAcumulado }),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao atualizar a meta."));
}

export async function excluirMeta(id: number): Promise<void> {
  const res = await fetch(`${PUBLIC_API_URL}${API_PREFIX}/metas/${id}`, {
    method: "DELETE",
    headers: await authHeadersClient(),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao excluir a meta."));
}

export async function criarDespesaFixa(despesa: {
  nome: string;
  categoria: string;
  valor_mensal: number;
  tipo: TipoDespesaFixa;
  data_inicio: string;
  parcela_atual?: number;
  parcelas_totais?: number;
}): Promise<void> {
  const res = await fetch(`${PUBLIC_API_URL}${API_PREFIX}/despesas-fixas`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeadersClient()) },
    body: JSON.stringify(despesa),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao salvar a despesa fixa."));
}

export async function atualizarParcelaDespesaFixa(id: number, parcelaAtual: number): Promise<void> {
  const res = await fetch(`${PUBLIC_API_URL}${API_PREFIX}/despesas-fixas/${id}/parcela`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...(await authHeadersClient()) },
    body: JSON.stringify({ parcela_atual: parcelaAtual }),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao atualizar a parcela."));
}

export async function encerrarDespesaFixa(id: number): Promise<void> {
  const res = await fetch(`${PUBLIC_API_URL}${API_PREFIX}/despesas-fixas/${id}/encerrar`, {
    method: "POST",
    headers: await authHeadersClient(),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao encerrar a despesa fixa."));
}

export async function excluirDespesaFixa(id: number): Promise<void> {
  const res = await fetch(`${PUBLIC_API_URL}${API_PREFIX}/despesas-fixas/${id}`, {
    method: "DELETE",
    headers: await authHeadersClient(),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao excluir a despesa fixa."));
}

export async function definirLimiteAlertaDespesasFixas(pct: number): Promise<void> {
  const res = await fetch(`${PUBLIC_API_URL}${API_PREFIX}/despesas-fixas/limite-alerta`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...(await authHeadersClient()) },
    body: JSON.stringify({ pct }),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao salvar o limite de alerta."));
}

export async function previewUpload(file: File): Promise<UploadPreview> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${PUBLIC_API_URL}${API_PREFIX}/upload/preview`, {
    method: "POST",
    body: formData,
    headers: await authHeadersClient(),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao ler o arquivo."));
  return res.json();
}

export async function persistUpload(file: File): Promise<UploadPersistSummary> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${PUBLIC_API_URL}${API_PREFIX}/upload/persist`, {
    method: "POST",
    body: formData,
    headers: await authHeadersClient(),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao importar o arquivo."));
  return res.json();
}

export async function aplicarCategoriaEmLote(
  description: string,
  category: string
): Promise<{ atualizadas: number; mensagem_treino: string }> {
  const res = await fetch(`${PUBLIC_API_URL}${API_PREFIX}/revisao/lote`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeadersClient()) },
    body: JSON.stringify({ description, category }),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao aplicar categoria em lote."));
  return res.json();
}

export async function confirmarRevisao(
  updates: { tx_hash: string; category: string }[]
): Promise<{ confirmadas: number; ainda_pendentes: number; mensagem_treino: string }> {
  const res = await fetch(`${PUBLIC_API_URL}${API_PREFIX}/revisao/confirmar`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeadersClient()) },
    body: JSON.stringify({ updates }),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao confirmar a revisão."));
  return res.json();
}

export async function retreinarModelo(): Promise<{ mensagem: string }> {
  const res = await fetch(`${PUBLIC_API_URL}${API_PREFIX}/revisao/retreinar`, {
    method: "POST",
    headers: await authHeadersClient(),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao re-treinar o modelo."));
  return res.json();
}

export async function gerarNarrativa(): Promise<NarrativaResponse> {
  const res = await fetch(`${PUBLIC_API_URL}${API_PREFIX}/narrativa`, {
    method: "POST",
    headers: await authHeadersClient(),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao gerar a explicação."));
  return res.json();
}

export async function baixarRelatorioPdf(month: string): Promise<Blob> {
  const url = new URL(`${PUBLIC_API_URL}${API_PREFIX}/relatorio/pdf`);
  url.searchParams.set("month", month);
  const res = await fetch(url, { headers: await authHeadersClient() });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao gerar o PDF."));
  return res.blob();
}

export async function enviarMensagemChat(mensagens: ChatMensagem[]): Promise<ChatResponse> {
  const res = await fetch(`${PUBLIC_API_URL}${API_PREFIX}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeadersClient()) },
    body: JSON.stringify({ mensagens }),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, "Falha ao enviar a mensagem."));
  return res.json();
}

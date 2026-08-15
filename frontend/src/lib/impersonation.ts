// "Visualizar como cliente" (recurso de assessor, ver sifp/api/auth.py::get_db):
// um cookie simples guarda o client_id que o assessor está visualizando.
// Não é httpOnly de propósito -- tanto api.ts (fetch do navegador) quanto
// api-server.ts (Server Components) precisam ler o mesmo valor pra anexar
// o header X-Sifra-Visualizar-Cliente em toda chamada, e api.ts roda no
// navegador. Um segundo cookie guarda só o e-mail, pra exibir no banner
// sem precisar de uma busca extra.
//
// Deliberadamente SEM "use client": só exporta funções (nada é executado
// na importação), então é seguro importar tanto de Client Components
// quanto de api-server.ts -- mesmo padrão de api.ts/api-server.ts.

export const CLIENTE_ID_COOKIE = "sifra_visualizando_cliente";
const CLIENTE_EMAIL_COOKIE = "sifra_visualizando_cliente_email";

// 8h -- prazo curto de propósito: é um modo de visualização temporário,
// não uma sessão; expira sozinho se o assessor esquecer de sair.
const MAX_AGE_SEGUNDOS = 8 * 60 * 60;

export function iniciarVisualizacaoCliente(clientId: string, clientEmail: string): void {
  document.cookie = `${CLIENTE_ID_COOKIE}=${clientId}; path=/; max-age=${MAX_AGE_SEGUNDOS}; samesite=lax`;
  document.cookie = `${CLIENTE_EMAIL_COOKIE}=${encodeURIComponent(clientEmail)}; path=/; max-age=${MAX_AGE_SEGUNDOS}; samesite=lax`;
}

export function encerrarVisualizacaoCliente(): void {
  document.cookie = `${CLIENTE_ID_COOKIE}=; path=/; max-age=0`;
  document.cookie = `${CLIENTE_EMAIL_COOKIE}=; path=/; max-age=0`;
}

function lerCookie(nome: string): string | null {
  if (typeof document === "undefined") return null;
  const alvo = `${nome}=`;
  const parte = document.cookie.split("; ").find((c) => c.startsWith(alvo));
  return parte ? parte.slice(alvo.length) : null;
}

export function clienteIdVisualizadoNoNavegador(): string | null {
  return lerCookie(CLIENTE_ID_COOKIE);
}

export function clienteVisualizadoNoNavegador(): { id: string; email: string } | null {
  const id = lerCookie(CLIENTE_ID_COOKIE);
  if (!id) return null;
  const email = lerCookie(CLIENTE_EMAIL_COOKIE);
  return { id, email: email ? decodeURIComponent(email) : id };
}

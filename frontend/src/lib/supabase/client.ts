import { createBrowserClient } from "@supabase/ssr";

// Cliente Supabase Auth pro navegador (Client Components) — usado só pra
// login/logout e ler a sessão atual. A chave "publishable" é pública por
// design (embutida no bundle do cliente), não é segredo.
//
// Instância única (singleton), NÃO uma nova a cada chamada -- várias
// telas (Perfil, sobretudo) montam vários componentes ao mesmo tempo que
// chamam createClient() em paralelo (PerfilForm, PasskeyCard,
// EmailImportacaoCard, AssessoresCard, CompletarCadastroCard,
// ExcluirContaCard). Múltiplas instâncias de GoTrueClient competindo pelo
// mesmo lock interno de refresh de sessão (Web Locks API) trava
// getSession()/getUser() num recarregamento forçado da página -- achado
// real testando o card de completar cadastro (nenhuma chamada pro
// backend saía do navegador, mas nenhum erro aparecia). Uma instância só,
// reaproveitada, elimina a disputa.
function novoCliente() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    // Passkeys (Face ID/Touch ID/Windows Hello) — beta da Supabase, precisa
    // desse opt-in explícito ou os métodos registerPasskey()/signInWithPasskey()
    // lançam erro. Login por senha continua funcionando normalmente.
    { auth: { experimental: { passkey: true } } }
  );
}

let client: ReturnType<typeof novoCliente> | null = null;

export function createClient() {
  if (!client) client = novoCliente();
  return client;
}

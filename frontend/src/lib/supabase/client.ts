import { createBrowserClient } from "@supabase/ssr";

// Cliente Supabase Auth pro navegador (Client Components) — usado só pra
// login/logout e ler a sessão atual. A chave "publishable" é pública por
// design (embutida no bundle do cliente), não é segredo.
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!
  );
}

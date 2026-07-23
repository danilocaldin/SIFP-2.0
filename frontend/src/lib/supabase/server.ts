import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

// Cliente Supabase Auth pro servidor (Server Components) — lê a sessão dos
// cookies pra saber quem está logado e pegar o access_token que vai no
// header Authorization das chamadas à API (sifp/api). Server Components
// não podem escrever cookie (só ler) — quem faz o refresh do token é o
// proxy.ts, que roda antes de toda página.
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            );
          } catch {
            // Chamado a partir de um Server Component — ignorado porque o
            // proxy.ts já cuida do refresh de sessão nesse caso.
          }
        },
      },
    }
  );
}

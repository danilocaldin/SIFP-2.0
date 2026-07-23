import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

// Lógica de refresh de sessão compartilhada com src/proxy.ts (arquivo
// próprio pra deixar a regra testável/legível separada do file convention
// do Next.js — o nome do arquivo "middleware" aqui é só descritivo, não é
// o file convention do Next, que a partir da v16 é "proxy.ts").
export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  // Essa chamada dispara o refresh do token quando expirado, escrevendo o
  // cookie novo na response acima (ver @supabase/ssr, padrão documentado
  // pra Next.js) — e devolve quem está logado (ou null), pro proxy.ts
  // decidir se redireciona (só quando SAAS_MODE está ligado).
  const {
    data: { user },
  } = await supabase.auth.getUser();

  return { response: supabaseResponse, user };
}

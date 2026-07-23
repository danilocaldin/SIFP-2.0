import { NextResponse, type NextRequest } from "next/server";

import { updateSession } from "@/lib/supabase/middleware";

// Convenção do Next.js 16+ (antigo "middleware.ts" — ver
// node_modules/next/dist/docs/.../file-conventions/proxy.md).
//
// Mesmo código-fonte serve dois deploys (ver decisão em
// project_sifp_multiuser_scaling): o Sifra pessoal do Danilo, sem login
// (NEXT_PUBLIC_SAAS_MODE não definida — proteção fica desligada, telas
// exatamente como sempre foram), e o SaaS multiusuário numa URL nova
// (NEXT_PUBLIC_SAAS_MODE=true — toda rota exige sessão, exceto /login).
const SAAS_MODE = process.env.NEXT_PUBLIC_SAAS_MODE === "true";

// Metadados de PWA (manifest, ícones, service worker) são buscados pelo
// próprio navegador/SO sem sessão nenhuma — o matcher abaixo já livra
// arquivos com extensão de imagem literal na URL, mas essas rotas são
// Route Handlers gerados (sem extensão na URL, ex: /icons/icon-192), então
// precisam de uma exceção explícita ou caem no redirect de login como
// qualquer outra página protegida.
const PUBLIC_PATHS = new Set(["/manifest.webmanifest", "/sw.js", "/apple-icon", "/icons/icon-192", "/icons/icon-512"]);

export async function proxy(request: NextRequest) {
  // No deploy pessoal (sem SAAS_MODE) as credenciais do Supabase nem
  // existem nesse projeto Vercel — nunca chama updateSession, que
  // quebraria toda rota tentando criar um cliente Supabase sem URL/chave.
  if (!SAAS_MODE) return NextResponse.next();

  const path = request.nextUrl.pathname;
  if (PUBLIC_PATHS.has(path)) return NextResponse.next();

  const { response, user } = await updateSession(request);

  const isLoginRoute = path === "/login";

  if (!user && !isLoginRoute) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  if (user && isLoginRoute) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};

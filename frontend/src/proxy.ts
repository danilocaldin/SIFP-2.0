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

export async function proxy(request: NextRequest) {
  const { response, user } = await updateSession(request);

  if (!SAAS_MODE) return response;

  const path = request.nextUrl.pathname;
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

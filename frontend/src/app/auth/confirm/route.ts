import { type EmailOtpType } from "@supabase/supabase-js";
import { type NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

// Rota de confirmação (Módulo SaaS Auth) — os links de convite/redefinição
// de senha do Supabase precisam apontar pra cá (?token_hash=...&type=...),
// não direto pro app, porque o cliente deste projeto usa o fluxo PKCE
// (@supabase/ssr força isso): o token vem por query param, verificado no
// SERVIDOR via verifyOtp(), não pelo fragmento #access_token= da URL que
// o template padrão de e-mail do Supabase ainda manda por default.
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const token_hash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;
  const next = searchParams.get("next") ?? "/";

  if (token_hash && type) {
    const supabase = await createClient();
    const { error } = await supabase.auth.verifyOtp({ type, token_hash });
    if (!error) {
      // "invite" e "recovery" autenticam mas não deixam senha nenhuma
      // definida — manda pra tela de login com o sinal certo em vez de
      // já entrar direto no app sem o usuário conseguir logar de novo depois.
      const destino = type === "invite" || type === "recovery" ? "/login?modo=definir-senha" : next;
      return NextResponse.redirect(new URL(destino, request.url));
    }
  }

  return NextResponse.redirect(new URL("/login?erro=link_invalido", request.url));
}

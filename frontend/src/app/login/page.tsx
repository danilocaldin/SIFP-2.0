"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { createClient } from "@/lib/supabase/client";

const LINK_INVALIDO_MSG =
  'Esse link expirou ou já foi usado. Peça um novo convite ou clique em "esqueci minha senha".';

// O template padrão de e-mail do Supabase (não dá pra customizar sem
// configurar SMTP próprio — ver docs/DECISOES_E_LICOES.md) manda o link
// de convite/recuperação de senha no formato antigo, com o token no
// FRAGMENTO da URL (#access_token=...&type=...). O cliente Supabase
// deste projeto (@supabase/ssr) força flowType "pkce" internamente e por
// isso RECUSA processar esse formato sozinho (erro silencioso, ver
// GoTrueClient._getSessionFromURL) — então o fragmento é lido e
// processado manualmente, e a sessão é estabelecida via setSession()
// (que não depende de flowType nenhum) em vez de confiar na detecção
// automática. Leitura pura, sem mutar nada — só pra descobrir o estado
// inicial correto antes da primeira renderização.
function readHashParams(): URLSearchParams | null {
  if (typeof window === "undefined" || !window.location.hash) return null;
  return new URLSearchParams(window.location.hash.slice(1));
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginPageContent />
    </Suspense>
  );
}

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [modo, setModo] = useState<"carregando" | "login" | "definir-senha">(() => {
    const hashParams = readHashParams();
    if (!hashParams) {
      return searchParams.get("modo") === "definir-senha" ? "definir-senha" : "login";
    }
    if (hashParams.get("error_code")) return "login";
    if (!hashParams.get("access_token") || !hashParams.get("refresh_token")) return "login";
    return "carregando"; // token presente — o efeito abaixo processa e decide o próximo modo
  });
  const [erroHash, setErroHash] = useState<string | null>(() =>
    readHashParams()?.get("error_code") ? LINK_INVALIDO_MSG : null
  );

  useEffect(() => {
    const hashParams = readHashParams();
    if (!hashParams) return;

    // Limpa o fragmento da URL imediatamente — nunca deixa o token
    // visível na barra de endereço/histórico mais tempo que o necessário.
    // (Não é setState, então não dispara o mesmo aviso de "cascading
    // renders" — é uma troca de histórico do navegador, não de estado do React.)
    window.history.replaceState(null, "", window.location.pathname + window.location.search);

    const accessToken = hashParams.get("access_token");
    const refreshToken = hashParams.get("refresh_token");
    const type = hashParams.get("type");
    if (!accessToken || !refreshToken) return;

    const supabase = createClient();
    supabase.auth.setSession({ access_token: accessToken, refresh_token: refreshToken }).then(({ error }) => {
      if (error) {
        setErroHash("Não foi possível validar o link. Tente pedir um novo.");
        setModo("login");
        return;
      }
      if (type === "invite" || type === "recovery") {
        setModo("definir-senha");
      } else {
        router.push("/");
        router.refresh();
      }
    });
  }, [router]);

  if (modo === "carregando") {
    return (
      <main className="flex min-h-screen w-full flex-1 items-center justify-center bg-background px-6" />
    );
  }

  return (
    <main className="flex min-h-screen w-full flex-1 items-center justify-center bg-background px-6">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center text-center">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/icon.svg" alt="Sifra" width={40} height={40} className="mb-2 rounded-[8px]" />
          <CardTitle className="font-display text-xl">
            {modo === "definir-senha" ? "Defina sua senha" : "Entrar no Sifra"}
          </CardTitle>
          <CardDescription>
            {modo === "definir-senha"
              ? "Primeiro acesso — escolha a senha que você vai usar daqui pra frente."
              : "Acesso por convite — use o e-mail e senha que você recebeu."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {erroHash && <p className="mb-4 text-sm text-destructive">{erroHash}</p>}
          {modo === "definir-senha" ? <DefinirSenhaForm /> : <LoginForm />}
        </CardContent>
      </Card>
    </main>
  );
}

function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    setCarregando(true);

    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({ email, password });

    if (error) {
      setErro("E-mail ou senha inválidos.");
      setCarregando(false);
      return;
    }

    router.push("/");
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="email">E-mail</Label>
        <Input
          id="email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="password">Senha</Label>
        <Input
          id="password"
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
      </div>
      {erro && <p className="text-sm text-destructive">{erro}</p>}
      <Button type="submit" disabled={carregando} className="mt-1">
        {carregando ? "Entrando…" : "Entrar"}
      </Button>
    </form>
  );
}

function DefinirSenhaForm() {
  const router = useRouter();
  const [senha, setSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);

    if (senha.length < 6) {
      setErro("A senha precisa ter pelo menos 6 caracteres.");
      return;
    }
    if (senha !== confirmacao) {
      setErro("As senhas não coincidem.");
      return;
    }

    setCarregando(true);
    const supabase = createClient();
    const { error } = await supabase.auth.updateUser({ password: senha });

    if (error) {
      setErro("Não foi possível salvar a senha. Tente novamente.");
      setCarregando(false);
      return;
    }

    router.push("/");
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="senha">Nova senha</Label>
        <Input
          id="senha"
          type="password"
          required
          value={senha}
          onChange={(e) => setSenha(e.target.value)}
          autoComplete="new-password"
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="confirmacao">Confirme a senha</Label>
        <Input
          id="confirmacao"
          type="password"
          required
          value={confirmacao}
          onChange={(e) => setConfirmacao(e.target.value)}
          autoComplete="new-password"
        />
      </div>
      {erro && <p className="text-sm text-destructive">{erro}</p>}
      <Button type="submit" disabled={carregando} className="mt-1">
        {carregando ? "Salvando…" : "Salvar senha e entrar"}
      </Button>
    </form>
  );
}

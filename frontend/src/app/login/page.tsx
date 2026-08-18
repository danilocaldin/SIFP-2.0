"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { createClient } from "@/lib/supabase/client";

// Achado real de auditoria: sem essa guarda, acessar /login no deploy
// pessoal (sem SAAS_MODE, sem as credenciais do Supabase configuradas
// nesse projeto Vercel) chamava createClient() que lança
// "supabaseUrl is required" de forma síncrona -- caía na tela genérica
// de erro em vez de simplesmente não existir, diferente do padrão já
// usado em /perfil pro mesmo cenário.
const SAAS_MODE = process.env.NEXT_PUBLIC_SAAS_MODE === "true";

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
  if (!SAAS_MODE) {
    return (
      <main className="flex min-h-[60vh] w-full flex-1 items-center justify-center px-6 text-center">
        <p className="text-sm text-muted-foreground">Essa página existe só no Sifra multiusuário.</p>
      </main>
    );
  }

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
  const [erroHash, setErroHash] = useState<string | null>(() => {
    if (readHashParams()?.get("error_code")) return LINK_INVALIDO_MSG;
    // /auth/confirm manda pra cá com ?erro=link_invalido quando o
    // verifyOtp() falha no servidor (token de convite/recuperação
    // inválido ou expirado) -- sem isso a pessoa só via um formulário de
    // login limpo, sem explicação nenhuma do que deu errado.
    if (searchParams.get("erro") === "link_invalido") return LINK_INVALIDO_MSG;
    return null;
  });

  useEffect(() => {
    // "modo" só chega aqui como "login" quando não há nem token no
    // fragmento nem ?modo=definir-senha na URL -- ou seja, não há
    // convite/recuperação em andamento. SÓ NESSE caso faz sentido
    // verificar se o visitante já está logado e mandar pra home; o
    // redirecionamento antigo ficava no proxy.ts (servidor) e por isso
    // interceptava tanto a volta do /auth/confirm (?modo=definir-senha,
    // sessão já criada no servidor) quanto o fragmento de um link de
    // recuperação clicado com outra sessão já ativa -- ver proxy.ts.
    if (modo !== "login") return;
    // Achado real de auditoria: sem essa checagem, um usuário que clica
    // num link de convite/recuperação vencido enquanto JÁ está logado
    // nesse navegador (por outro caminho) era redirecionado pra "/" antes
    // de conseguir ler "Esse link expirou ou já foi usado..." -- a
    // mensagem que /auth/confirm mandou mostrar (?erro=link_invalido)
    // nunca chegava a aparecer.
    if (erroHash) return;
    const supabase = createClient();
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) {
        router.replace("/");
      }
    });
  }, [modo, erroHash, router]);

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
    supabase.auth
      .setSession({ access_token: accessToken, refresh_token: refreshToken })
      .then(({ error }) => {
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
      })
      // Nunca deixa a tela travada em "carregando" pra sempre — qualquer
      // falha inesperada (token malformado, rede fora do ar) cai de volta
      // pro formulário normal de login com uma mensagem de erro.
      .catch(() => {
        setErroHash("Não foi possível validar o link. Tente pedir um novo.");
        setModo("login");
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
          {modo === "definir-senha" ? (
            <DefinirSenhaForm />
          ) : (
            <LoginForm onCodigoVerificado={() => setModo("definir-senha")} />
          )}
        </CardContent>
      </Card>
    </main>
  );
}

function LoginForm({ onCodigoVerificado }: { onCodigoVerificado: () => void }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [entrandoComPasskey, setEntrandoComPasskey] = useState(false);
  const [recuperar, setRecuperar] = useState(false);
  const [comCodigo, setComCodigo] = useState(false);

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

  async function handlePasskeyLogin() {
    setErro(null);
    setEntrandoComPasskey(true);

    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPasskey();

    setEntrandoComPasskey(false);
    if (error) {
      // Usuário cancelou o prompt do sistema — não é um erro pra mostrar.
      const cancelado = "code" in error && error.code === "ERROR_CEREMONY_ABORTED";
      if (!cancelado) {
        setErro("Não foi possível entrar com Face ID/Touch ID. Use e-mail e senha.");
      }
      return;
    }

    router.push("/");
    router.refresh();
  }

  if (recuperar) {
    return <RecuperarSenhaForm emailInicial={email} onVoltar={() => setRecuperar(false)} />;
  }

  if (comCodigo) {
    return (
      <CodigoForm
        emailInicial={email}
        onSucesso={onCodigoVerificado}
        onVoltar={() => setComCodigo(false)}
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Button
        type="button"
        variant="outline"
        disabled={entrandoComPasskey}
        onClick={handlePasskeyLogin}
      >
        {entrandoComPasskey ? "Aguardando confirmação…" : "🆔 Entrar com Face ID / Touch ID"}
      </Button>

      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <div className="h-px flex-1 bg-border" />
        ou
        <div className="h-px flex-1 bg-border" />
      </div>

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
        <button
          type="button"
          onClick={() => setRecuperar(true)}
          className="text-sm text-muted-foreground underline-offset-2 hover:underline"
        >
          Esqueci minha senha
        </button>
        <button
          type="button"
          onClick={() => setComCodigo(true)}
          className="text-sm text-muted-foreground underline-offset-2 hover:underline"
        >
          Recebi um código de acesso
        </button>
      </form>
    </div>
  );
}

function CodigoForm({
  emailInicial,
  onSucesso,
  onVoltar,
}: {
  emailInicial: string;
  onSucesso: () => void;
  onVoltar: () => void;
}) {
  const [email, setEmail] = useState(emailInicial);
  const [codigo, setCodigo] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    setCarregando(true);

    const supabase = createClient();
    const codigoLimpo = codigo.trim();
    // O código serve tanto pra "esqueci minha senha" (recovery) quanto
    // pra convite de conta nova (invite) -- não dá pra saber qual é só
    // olhando o código, então tenta os dois tipos em sequência antes de
    // desistir, sem pedir pra pessoa escolher uma opção técnica que ela
    // não tem como saber responder.
    let { error } = await supabase.auth.verifyOtp({ email, token: codigoLimpo, type: "recovery" });
    if (error) {
      ({ error } = await supabase.auth.verifyOtp({ email, token: codigoLimpo, type: "invite" }));
    }

    setCarregando(false);
    if (error) {
      setErro("Código inválido ou expirado. Confira o e-mail e o código, ou peça um novo.");
      return;
    }
    onSucesso();
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Digite o e-mail e o código de acesso que você recebeu (não é a senha).
      </p>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="email-codigo">E-mail</Label>
        <Input
          id="email-codigo"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="codigo">Código de acesso</Label>
        <Input
          id="codigo"
          type="text"
          required
          inputMode="numeric"
          autoComplete="one-time-code"
          value={codigo}
          onChange={(e) => setCodigo(e.target.value)}
        />
      </div>
      {erro && <p className="text-sm text-destructive">{erro}</p>}
      <Button type="submit" disabled={carregando} className="mt-1">
        {carregando ? "Verificando…" : "Continuar"}
      </Button>
      <button
        type="button"
        onClick={onVoltar}
        className="text-sm text-muted-foreground underline-offset-2 hover:underline"
      >
        Voltar pro login
      </button>
    </form>
  );
}

function RecuperarSenhaForm({ emailInicial, onVoltar }: { emailInicial: string; onVoltar: () => void }) {
  const [email, setEmail] = useState(emailInicial);
  const [enviado, setEnviado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    setCarregando(true);

    const supabase = createClient();
    // Sem redirectTo, o Supabase manda pra "Site URL" do projeto (a raiz
    // do site) — só /login sabe ler o token do link e virar a tela de
    // definir senha nova, então precisa apontar pra lá explicitamente.
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/login`,
    });

    setCarregando(false);
    if (error) {
      setErro("Não foi possível enviar o link. Tente novamente.");
      return;
    }
    setEnviado(true);
  }

  if (enviado) {
    return (
      <div className="flex flex-col gap-4">
        <p className="text-sm text-muted-foreground">
          Se esse e-mail estiver cadastrado, você vai receber um link pra definir uma senha nova.
        </p>
        <button
          type="button"
          onClick={onVoltar}
          className="text-sm text-muted-foreground underline-offset-2 hover:underline"
        >
          Voltar pro login
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="email-recuperar">E-mail</Label>
        <Input
          id="email-recuperar"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
        />
      </div>
      {erro && <p className="text-sm text-destructive">{erro}</p>}
      <Button type="submit" disabled={carregando} className="mt-1">
        {carregando ? "Enviando…" : "Enviar link de recuperação"}
      </Button>
      <button
        type="button"
        onClick={onVoltar}
        className="text-sm text-muted-foreground underline-offset-2 hover:underline"
      >
        Voltar pro login
      </button>
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
      // Sessão de recuperação pode ter expirado (link antigo, ex: um
      // pedido de reset anterior enquanto esperava o e-mail atrasar) —
      // mostra a mensagem real do Supabase em vez de um genérico, pra dar
      // pro usuário (e pra depuração) o motivo de verdade.
      setErro(`Não foi possível salvar a senha: ${error.message}. Peça um novo link e tente de novo.`);
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

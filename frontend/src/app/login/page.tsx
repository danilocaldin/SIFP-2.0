"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { createClient } from "@/lib/supabase/client";

export default function LoginPage() {
  // O Supabase Auth manda o link de convite (e o de "esqueci a senha")
  // com um token no fragmento da URL (#access_token=...) — o cliente
  // já autentica a sessão sozinho ao ser criado (detectSessionInUrl),
  // mas ainda falta uma senha de verdade. onAuthStateChange dispara o
  // evento PASSWORD_RECOVERY nesse caso (mesmo evento pros dois fluxos,
  // convite e recuperação) — é o sinal pra trocar o formulário de login
  // por um de "defina sua senha", em vez de pedir uma senha que o
  // usuário convidado ainda não tem.
  const [modo, setModo] = useState<"login" | "definir-senha">("login");

  useEffect(() => {
    const supabase = createClient();
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event) => {
      if (event === "PASSWORD_RECOVERY") {
        setModo("definir-senha");
      }
    });
    return () => subscription.unsubscribe();
  }, []);

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

"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getEmailImportacao, resetarRemetenteEmailImportacao } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

const SAAS_MODE = process.env.NEXT_PUBLIC_SAAS_MODE === "true";

export default function PerfilPage() {
  if (!SAAS_MODE) {
    return (
      <main className="mx-auto flex min-h-[60vh] w-full max-w-lg flex-1 items-center justify-center px-6 text-center">
        <p className="text-sm text-muted-foreground">Essa página existe só no Sifra multiusuário.</p>
      </main>
    );
  }

  return <PerfilForm />;
}

function PerfilForm() {
  const [nome, setNome] = useState("");
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [salvo, setSalvo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      setNome((data.user?.user_metadata?.full_name as string | undefined) ?? "");
      setCarregando(false);
    });
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSalvando(true);
    setErro(null);
    setSalvo(false);

    const supabase = createClient();
    const { error } = await supabase.auth.updateUser({ data: { full_name: nome.trim() } });

    setSalvando(false);
    if (error) {
      setErro("Não foi possível salvar. Tente novamente.");
      return;
    }
    setSalvo(true);
  }

  return (
    <main className="mx-auto w-full max-w-lg flex-1 px-6 py-12 sm:py-16">
      <p className="text-sm font-medium text-muted-foreground">Perfil</p>
      <h1 className="mt-1 text-xl font-semibold">Seus dados</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Usado para identificar seus relatórios — por exemplo, na capa do relatório em PDF.
      </p>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-base">Nome completo</CardTitle>
          <CardDescription>Como você quer ser identificado nos seus documentos.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="nome">Nome completo</Label>
              <Input
                id="nome"
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                disabled={carregando}
                placeholder="Seu nome completo"
              />
            </div>
            {erro && <p className="text-sm text-destructive">{erro}</p>}
            <div className="flex items-center gap-3">
              <Button type="submit" disabled={carregando || salvando || !nome.trim()}>
                {salvando ? "Salvando…" : "Salvar"}
              </Button>
              {salvo && <span className="text-sm text-muted-foreground">Salvo.</span>}
            </div>
          </form>
        </CardContent>
      </Card>

      <PasskeyCard />
      <EmailImportacaoCard />
    </main>
  );
}

type PasskeyItem = {
  id: string;
  friendly_name?: string;
  created_at: string;
  last_used_at?: string;
};

function PasskeyCard() {
  const [passkeys, setPasskeys] = useState<PasskeyItem[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [registrando, setRegistrando] = useState(false);
  const [excluindoId, setExcluindoId] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  async function buscarPasskeys(): Promise<PasskeyItem[]> {
    const supabase = createClient();
    const { data, error } = await supabase.auth.passkey.list();
    return error ? [] : (data ?? []);
  }

  useEffect(() => {
    buscarPasskeys()
      .then(setPasskeys)
      .finally(() => setCarregando(false));
  }, []);

  async function handleRegistrar() {
    setRegistrando(true);
    setErro(null);
    const supabase = createClient();
    const { error } = await supabase.auth.registerPasskey();
    setRegistrando(false);
    if (error) {
      // Usuário cancelou o prompt do Face ID/Touch ID — não é um erro real.
      const cancelado = "code" in error && error.code === "ERROR_CEREMONY_ABORTED";
      if (!cancelado) {
        setErro("Não foi possível cadastrar. Tente novamente.");
      }
      return;
    }
    setPasskeys(await buscarPasskeys());
  }

  async function handleExcluir(passkeyId: string) {
    if (!window.confirm("Excluir esta passkey? Você não vai mais conseguir entrar com biometria neste dispositivo.")) {
      return;
    }
    setExcluindoId(passkeyId);
    setErro(null);
    const supabase = createClient();
    const { error } = await supabase.auth.passkey.delete({ passkeyId });
    setExcluindoId(null);
    if (error) {
      setErro("Não foi possível excluir. Tente novamente.");
      return;
    }
    setPasskeys((prev) => prev.filter((p) => p.id !== passkeyId));
  }

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle className="text-base">Entrar com Face ID / Touch ID</CardTitle>
        <CardDescription>
          Cadastre este dispositivo para entrar no Sifra com biometria, sem digitar senha. Cada
          dispositivo (celular, notebook) precisa ser cadastrado separadamente.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!carregando && passkeys.length > 0 && (
          <ul className="space-y-2">
            {passkeys.map((p) => (
              <li
                key={p.id}
                className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm"
              >
                <span>
                  {p.friendly_name || "Dispositivo sem nome"}
                  <span className="block text-xs text-muted-foreground">
                    Cadastrado em {new Date(p.created_at).toLocaleDateString("pt-BR")}
                    {p.last_used_at &&
                      ` · último uso em ${new Date(p.last_used_at).toLocaleDateString("pt-BR")}`}
                  </span>
                </span>
                <button
                  type="button"
                  className="text-xs text-muted-foreground hover:text-red-700 dark:hover:text-red-400 disabled:opacity-50"
                  disabled={excluindoId === p.id}
                  onClick={() => handleExcluir(p.id)}
                  title="Excluir passkey"
                >
                  {excluindoId === p.id ? "…" : "🗑️"}
                </button>
              </li>
            ))}
          </ul>
        )}
        {erro && <p className="text-sm text-destructive">{erro}</p>}
        <Button type="button" variant="outline" disabled={registrando} onClick={handleRegistrar}>
          {registrando ? "Aguardando confirmação…" : "+ Cadastrar este dispositivo"}
        </Button>
      </CardContent>
    </Card>
  );
}

function EmailImportacaoCard() {
  const [email, setEmail] = useState<string | null>(null);
  const [remetenteConfiavel, setRemetenteConfiavel] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [copiado, setCopiado] = useState(false);
  const [resetando, setResetando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  function aplicarResultado(r: Awaited<ReturnType<typeof getEmailImportacao>>) {
    setEmail(r?.email ?? null);
    setRemetenteConfiavel(r?.remetente_confiavel ?? null);
  }

  useEffect(() => {
    getEmailImportacao()
      .then(aplicarResultado)
      .finally(() => setCarregando(false));
  }, []);

  async function handleCopiar() {
    if (!email) return;
    await navigator.clipboard.writeText(email);
    setCopiado(true);
    setTimeout(() => setCopiado(false), 2000);
  }

  async function handleResetar() {
    setResetando(true);
    setErro(null);
    try {
      await resetarRemetenteEmailImportacao();
      aplicarResultado(await getEmailImportacao());
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro desconhecido.");
    } finally {
      setResetando(false);
    }
  }

  if (carregando || !email) return null;

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle className="text-base">Importação automática por e-mail</CardTitle>
        <CardDescription>
          Configure um encaminhamento automático no seu e-mail para este endereço — assim, o
          extrato mensal do BTG entra no Sifra sozinho, sem precisar baixar e subir o arquivo.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2">
          <code className="flex-1 rounded-md border border-border bg-muted px-3 py-2 text-sm break-all">
            {email}
          </code>
          <Button type="button" variant="outline" onClick={handleCopiar}>
            {copiado ? "Copiado!" : "Copiar"}
          </Button>
        </div>

        <div className="text-xs text-muted-foreground">
          {remetenteConfiavel ? (
            <p>
              Por segurança, só e-mails vindos de <strong>{remetenteConfiavel}</strong> são
              aceitos nesse endereço.{" "}
              <button
                type="button"
                onClick={handleResetar}
                disabled={resetando}
                className="underline underline-offset-2 hover:text-foreground disabled:opacity-50"
              >
                {resetando ? "Trocando…" : "Mudei de e-mail de encaminhamento"}
              </button>
            </p>
          ) : (
            <p>
              Ainda não recebemos nenhum e-mail nesse endereço. O primeiro remetente que enviar
              um extrato aqui vira o único aceito daqui pra frente (proteção contra alguém tentar
              enviar um extrato falso, mesmo que descubra esse endereço).
            </p>
          )}
        </div>
        {erro && <p className="text-xs text-destructive">⚠️ {erro}</p>}
      </CardContent>
    </Card>
  );
}

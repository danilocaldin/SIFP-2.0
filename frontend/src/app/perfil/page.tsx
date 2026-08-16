"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  aceitarVinculoAssessor,
  excluirConta,
  getEmailImportacao,
  listarVinculosCliente,
  resetarRemetenteEmailImportacao,
  revogarVinculoPeloCliente,
} from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type { VinculoAssessor } from "@/lib/types";

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
      <AssessoresCard />
      <ExcluirContaCard />
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
    if (error) throw error;
    return data ?? [];
  }

  useEffect(() => {
    buscarPasskeys()
      .then(setPasskeys)
      .catch(() => setErro("Não foi possível carregar seus dispositivos cadastrados. Tente recarregar a página."))
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
    try {
      setPasskeys(await buscarPasskeys());
    } catch {
      setErro("Dispositivo cadastrado, mas não foi possível atualizar a lista. Recarregue a página.");
    }
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
                  aria-label={`Excluir passkey: ${p.friendly_name || "Dispositivo sem nome"}`}
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
      .catch((err) => setErro(err instanceof Error ? err.message : "Erro desconhecido."))
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

  if (carregando) return null;
  // Sem e-mail E sem erro: recurso legitimamente não configurado nesse
  // deploy (503) -- aí sim o card não se aplica e fica invisível. Com
  // erro, mostra o card com a mensagem em vez de sumir sem explicação
  // (achado real de auditoria: antes, qualquer falha de rede/servidor
  // fazia o card inteiro desaparecer, indistinguível de "não existe").
  if (!email && !erro) return null;

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
        {email && (
          <>
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
          </>
        )}
        {erro && <p className="text-xs text-destructive">⚠️ {erro}</p>}
      </CardContent>
    </Card>
  );
}

function formatarData(iso: string | null): string | null {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function AssessoresCard() {
  const [vinculos, setVinculos] = useState<VinculoAssessor[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [emAndamentoId, setEmAndamentoId] = useState<number | null>(null);

  async function atualizarLista() {
    try {
      setVinculos(await listarVinculosCliente());
      setErro(null);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro desconhecido.");
    }
  }

  useEffect(() => {
    // Chamada encadeada direto no efeito (não uma função local chamando
    // setState) -- mesmo padrão do resto desta página, satisfaz
    // react-hooks/set-state-in-effect.
    listarVinculosCliente()
      .then((data) => {
        setVinculos(data);
        setErro(null);
      })
      .catch((err) => setErro(err instanceof Error ? err.message : "Erro desconhecido."))
      .finally(() => setCarregando(false));
  }, []);

  async function handleAceitar(v: VinculoAssessor) {
    setEmAndamentoId(v.id);
    setErro(null);
    try {
      await aceitarVinculoAssessor(v.id);
      await atualizarLista();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro desconhecido.");
    } finally {
      setEmAndamentoId(null);
    }
  }

  async function handleRecusarOuRevogar(v: VinculoAssessor, confirmar: string) {
    if (!window.confirm(confirmar)) return;
    setEmAndamentoId(v.id);
    setErro(null);
    try {
      await revogarVinculoPeloCliente(v.id);
      await atualizarLista();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro desconhecido.");
    } finally {
      setEmAndamentoId(null);
    }
  }

  if (carregando) return null;
  // Revogado pelo próprio cliente: já sabe, não precisa continuar vendo.
  // Revogado pelo assessor (revogado_por != client_id): fica visível como
  // aviso -- é o mecanismo de "avisar o cliente" acordado com o Danilo,
  // sem precisar de e-mail/notificação separada.
  const visiveis = vinculos.filter((v) => v.status !== "revogado" || v.revogado_por !== v.client_id);
  if (visiveis.length === 0 && !erro) return null;

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle className="text-base">Assessores com acesso aos seus dados</CardTitle>
        <CardDescription>
          Acesso somente leitura — um assessor vinculado vê os mesmos dados que você, exceto seu
          histórico de chat e esta tela de Perfil. Você pode revogar a qualquer momento.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {erro && <p className="text-sm text-destructive">{erro}</p>}
        {visiveis.length > 0 && (
          <ul className="space-y-2">
            {visiveis.map((v) => (
              <li key={v.id} className="rounded-md border border-border px-3 py-2.5">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{v.advisor_email ?? "Assessor"}</p>
                    <p className="text-xs text-muted-foreground">
                      {v.status === "pendente" && `Convite recebido em ${formatarData(v.convidado_em)}`}
                      {v.status === "aceito" && `Acesso concedido em ${formatarData(v.aceito_em)}`}
                      {v.status === "revogado" &&
                        `Acesso revogado pelo assessor em ${formatarData(v.revogado_em)}`}
                    </p>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-2">
                    {v.status === "pendente" && (
                      <Badge variant="secondary">Convite pendente</Badge>
                    )}
                    {v.status === "aceito" && <Badge variant="default">Ativo</Badge>}
                    {v.status === "revogado" && <Badge variant="outline">Revogado</Badge>}
                    {v.status === "pendente" && (
                      <>
                        <Button
                          type="button"
                          size="sm"
                          disabled={emAndamentoId === v.id}
                          onClick={() => handleAceitar(v)}
                        >
                          Aceitar
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={emAndamentoId === v.id}
                          onClick={() =>
                            handleRecusarOuRevogar(
                              v,
                              `Recusar o convite de ${v.advisor_email ?? "esse assessor"}?`
                            )
                          }
                        >
                          Recusar
                        </Button>
                      </>
                    )}
                    {v.status === "aceito" && (
                      <button
                        type="button"
                        className="text-xs text-muted-foreground hover:text-red-700 disabled:opacity-50 dark:hover:text-red-400"
                        disabled={emAndamentoId === v.id}
                        onClick={() =>
                          handleRecusarOuRevogar(
                            v,
                            `Revogar o acesso de ${v.advisor_email ?? "esse assessor"} aos seus dados?`
                          )
                        }
                        title="Revogar acesso"
                        aria-label={`Revogar acesso: ${v.advisor_email ?? "assessor"}`}
                      >
                        {emAndamentoId === v.id ? "…" : "🗑️"}
                      </button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function ExcluirContaCard() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [confirmando, setConfirmando] = useState(false);
  const [emailDigitado, setEmailDigitado] = useState("");
  const [excluindo, setExcluindo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => setEmail(data.user?.email ?? null));
  }, []);

  function handleCancelar() {
    setConfirmando(false);
    setEmailDigitado("");
    setErro(null);
  }

  async function handleExcluir() {
    setExcluindo(true);
    setErro(null);
    try {
      await excluirConta();
      const supabase = createClient();
      await supabase.auth.signOut();
      router.push("/login");
      router.refresh();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro desconhecido.");
      setExcluindo(false);
    }
  }

  const confirmacaoValida = email !== null && emailDigitado.trim().toLowerCase() === email.toLowerCase();

  return (
    <Card className="mt-6 border-destructive/30">
      <CardHeader>
        <CardTitle className="text-base text-destructive">Excluir minha conta</CardTitle>
        <CardDescription>
          Apaga permanentemente sua conta e todos os seus dados no Sifra — transações, patrimônio,
          orçamento, metas, despesas fixas e vínculos com assessores. Não tem como desfazer.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!confirmando && (
          <Button type="button" variant="destructive" onClick={() => setConfirmando(true)}>
            Excluir minha conta
          </Button>
        )}
        {confirmando && (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-destructive">
              Essa ação é definitiva. Pra confirmar, digite seu e-mail ({email ?? "…"}) abaixo.
            </p>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="confirmar-exclusao">Digite seu e-mail pra confirmar</Label>
              <Input
                id="confirmar-exclusao"
                value={emailDigitado}
                onChange={(e) => setEmailDigitado(e.target.value)}
                placeholder={email ?? ""}
                disabled={excluindo}
                autoComplete="off"
              />
            </div>
            {erro && <p className="text-sm text-destructive">{erro}</p>}
            <div className="flex items-center gap-3">
              <Button
                type="button"
                variant="destructive"
                disabled={!confirmacaoValida || excluindo}
                onClick={handleExcluir}
              >
                {excluindo ? "Excluindo…" : "Excluir permanentemente"}
              </Button>
              <Button type="button" variant="outline" disabled={excluindo} onClick={handleCancelar}>
                Cancelar
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

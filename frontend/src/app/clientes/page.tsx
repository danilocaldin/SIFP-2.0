"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { convidarCliente, listarClientesAssessor, revogarClientePeloAssessor } from "@/lib/api";
import { iniciarVisualizacaoCliente } from "@/lib/impersonation";
import type { StatusVinculoAssessor, VinculoAssessor } from "@/lib/types";

const SAAS_MODE = process.env.NEXT_PUBLIC_SAAS_MODE === "true";

export default function ClientesPage() {
  if (!SAAS_MODE) {
    return (
      <main className="mx-auto flex min-h-[60vh] w-full max-w-lg flex-1 items-center justify-center px-6 text-center">
        <p className="text-sm text-muted-foreground">Essa página existe só no Sifra multiusuário.</p>
      </main>
    );
  }

  return <ClientesConteudo />;
}

function statusBadge(status: StatusVinculoAssessor) {
  if (status === "aceito") return <Badge variant="default">Ativo</Badge>;
  if (status === "pendente") return <Badge variant="secondary">Convite pendente</Badge>;
  return <Badge variant="outline">Revogado</Badge>;
}

function formatarData(iso: string | null): string | null {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function ClientesConteudo() {
  const router = useRouter();
  const [vinculos, setVinculos] = useState<VinculoAssessor[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [convidando, setConvidando] = useState(false);
  const [erroConvite, setErroConvite] = useState<string | null>(null);

  const [emAndamentoId, setEmAndamentoId] = useState<number | null>(null);

  // Recarrega a lista depois de uma mutação (convidar/revogar) -- não
  // mexe em `carregando`, que só cobre a busca inicial (ver useEffect).
  async function atualizarLista() {
    try {
      setVinculos(await listarClientesAssessor());
      setErro(null);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro desconhecido.");
    }
  }

  useEffect(() => {
    // Chamada encadeada (.then/.catch/.finally) direto no corpo do efeito,
    // não uma função local chamando setState -- mesmo padrão já usado em
    // perfil/page.tsx (PasskeyCard/EmailImportacaoCard), satisfaz
    // react-hooks/set-state-in-effect.
    listarClientesAssessor()
      .then((data) => {
        setVinculos(data);
        setErro(null);
      })
      .catch((err) => setErro(err instanceof Error ? err.message : "Erro desconhecido."))
      .finally(() => setCarregando(false));
  }, []);

  async function handleConvidar(e: React.FormEvent) {
    e.preventDefault();
    setConvidando(true);
    setErroConvite(null);
    try {
      await convidarCliente(email.trim());
      setEmail("");
      await atualizarLista();
    } catch (err) {
      setErroConvite(err instanceof Error ? err.message : "Erro desconhecido.");
    } finally {
      setConvidando(false);
    }
  }

  function handleVisualizar(v: VinculoAssessor) {
    if (!v.client_id) return;
    iniciarVisualizacaoCliente(v.client_id, v.client_email);
    router.push("/");
    router.refresh();
  }

  async function handleRevogar(v: VinculoAssessor) {
    if (!window.confirm(`Revogar o acesso aos dados de ${v.client_email}? Você pode convidar de novo depois.`)) {
      return;
    }
    setEmAndamentoId(v.id);
    setErro(null);
    try {
      await revogarClientePeloAssessor(v.id);
      await atualizarLista();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro desconhecido.");
    } finally {
      setEmAndamentoId(null);
    }
  }

  return (
    <main className="mx-auto w-full max-w-2xl flex-1 px-6 py-12 sm:py-16">
      <p className="text-sm font-medium text-muted-foreground">Clientes</p>
      <h1 className="mt-1 text-xl font-semibold">Acesso somente leitura aos dados dos seus clientes</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Convide um cliente pelo e-mail que ele usa (ou vai usar) no Sifra. O acesso só começa depois
        que ele aceitar o convite, e ele pode revogar a qualquer momento.
      </p>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-base">Convidar cliente</CardTitle>
          <CardDescription>
            Se o e-mail já tiver conta no Sifra, o convite aparece pra ele assim que fizer login.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleConvidar} className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex flex-1 flex-col gap-1.5">
              <Label htmlFor="email-cliente">E-mail do cliente</Label>
              <Input
                id="email-cliente"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="cliente@exemplo.com"
                disabled={convidando}
              />
            </div>
            <Button type="submit" disabled={convidando || !email.trim()}>
              {convidando ? "Enviando…" : "Convidar"}
            </Button>
          </form>
          {erroConvite && <p className="mt-2 text-sm text-destructive">{erroConvite}</p>}
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-base">Seus clientes</CardTitle>
          <CardDescription>Convites enviados, ativos e revogados.</CardDescription>
        </CardHeader>
        <CardContent>
          {carregando && <p className="text-sm text-muted-foreground">Carregando…</p>}
          {!carregando && erro && <p className="text-sm text-destructive">{erro}</p>}
          {!carregando && !erro && vinculos.length === 0 && (
            <p className="text-sm text-muted-foreground">Nenhum cliente convidado ainda.</p>
          )}
          {!carregando && !erro && vinculos.length > 0 && (
            <ul className="space-y-2">
              {vinculos.map((v) => (
                <li
                  key={v.id}
                  className="flex flex-col gap-2 rounded-md border border-border px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{v.client_email}</p>
                    <p className="text-xs text-muted-foreground">
                      {statusBadgeText(v)}
                    </p>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-2">
                    {statusBadge(v.status)}
                    {v.status === "aceito" && (
                      <Button type="button" size="sm" variant="outline" onClick={() => handleVisualizar(v)}>
                        Visualizar
                      </Button>
                    )}
                    {(v.status === "pendente" || v.status === "aceito") && (
                      <button
                        type="button"
                        className="text-xs text-muted-foreground hover:text-red-700 disabled:opacity-50 dark:hover:text-red-400"
                        disabled={emAndamentoId === v.id}
                        onClick={() => handleRevogar(v)}
                        title="Revogar acesso"
                        aria-label={`Revogar acesso: ${v.client_email}`}
                      >
                        {emAndamentoId === v.id ? "…" : "🗑️"}
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </main>
  );
}

function statusBadgeText(v: VinculoAssessor): string {
  if (v.status === "aceito") {
    const data = formatarData(v.aceito_em);
    return data ? `Aceito em ${data}` : "Aceito";
  }
  if (v.status === "pendente") {
    const data = formatarData(v.convidado_em);
    return data ? `Convidado em ${data}` : "Convite enviado";
  }
  const data = formatarData(v.revogado_em);
  return data ? `Revogado em ${data}` : "Revogado";
}

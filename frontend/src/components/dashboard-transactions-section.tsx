"use client";

import { useState } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getDashboardTransacoes } from "@/lib/api";
import { formatBRL } from "@/lib/format";
import type { DashboardTransaction } from "@/lib/types";

const PAGE_SIZE = 200;

export function DashboardTransactionsSection({ month }: { month: string | null }) {
  const [aberto, setAberto] = useState(false);
  const [transacoes, setTransacoes] = useState<DashboardTransaction[]>([]);
  const [total, setTotal] = useState(0);
  const [temMais, setTemMais] = useState(false);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function carregarPagina(offset: number) {
    setCarregando(true);
    setErro(null);
    try {
      const pagina = await getDashboardTransacoes(month, PAGE_SIZE, offset);
      setTransacoes((prev) => (offset === 0 ? pagina.transactions : [...prev, ...pagina.transactions]));
      setTotal(pagina.total);
      setTemMais(pagina.has_more);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro desconhecido.");
    } finally {
      setCarregando(false);
    }
  }

  function handleToggle(e: React.SyntheticEvent<HTMLDetailsElement>) {
    const abrindo = e.currentTarget.open;
    setAberto(abrindo);
    if (abrindo && transacoes.length === 0 && !carregando) {
      carregarPagina(0);
    }
  }

  return (
    <details className="mt-10 rounded-lg border border-border p-4 text-sm" onToggle={handleToggle}>
      <summary className="cursor-pointer font-medium text-foreground">
        Ver todas as transações do período
      </summary>

      {aberto && (
        <div className="mt-4">
          {erro ? (
            <p className="text-sm text-destructive">⚠️ {erro}</p>
          ) : transacoes.length === 0 && carregando ? (
            <p className="text-sm text-muted-foreground">Carregando…</p>
          ) : transacoes.length === 0 ? (
            <p className="text-sm text-muted-foreground">Sem transações no período selecionado.</p>
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Data</TableHead>
                      <TableHead>Descrição</TableHead>
                      <TableHead className="text-right">Valor</TableHead>
                      <TableHead>Categoria do banco</TableHead>
                      <TableHead>Estabelecimento</TableHead>
                      <TableHead>Categoria</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {transacoes.map((t, i) => (
                      <TableRow key={`${t.date}-${t.description}-${i}`}>
                        <TableCell className="text-muted-foreground">{t.date}</TableCell>
                        <TableCell>{t.description}</TableCell>
                        <TableCell className="text-right">{formatBRL(t.value)}</TableCell>
                        <TableCell className="text-muted-foreground">{t.bank_category || "—"}</TableCell>
                        <TableCell className="text-muted-foreground">{t.merchant || "—"}</TableCell>
                        <TableCell className="text-muted-foreground">{t.category}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                Mostrando {transacoes.length} de {total} transações.
              </p>
              {temMais && (
                <button
                  type="button"
                  onClick={() => carregarPagina(transacoes.length)}
                  disabled={carregando}
                  className="mt-2 text-xs font-medium text-foreground hover:underline disabled:opacity-50"
                >
                  {carregando ? "Carregando…" : "Carregar mais"}
                </button>
              )}
            </>
          )}
        </div>
      )}
    </details>
  );
}

"use client";

import { useState } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getPatrimonioSnapshots } from "@/lib/api";
import { formatBRL, formatPct } from "@/lib/format";
import type { AssetPosition } from "@/lib/types";

const PAGE_SIZE = 200;

export function PatrimonioSnapshotsSection() {
  const [aberto, setAberto] = useState(false);
  const [snapshots, setSnapshots] = useState<AssetPosition[]>([]);
  const [total, setTotal] = useState(0);
  const [temMais, setTemMais] = useState(false);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function carregarPagina(offset: number) {
    setCarregando(true);
    setErro(null);
    try {
      const pagina = await getPatrimonioSnapshots(PAGE_SIZE, offset);
      setSnapshots((prev) => (offset === 0 ? pagina.snapshots : [...prev, ...pagina.snapshots]));
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
    if (abrindo && snapshots.length === 0 && !carregando) {
      carregarPagina(0);
    }
  }

  return (
    <details className="mt-10 rounded-lg border border-border p-4 text-sm" onToggle={handleToggle}>
      <summary className="cursor-pointer font-medium text-foreground">
        Ver histórico completo (todos os snapshots importados)
      </summary>

      {aberto && (
        <div className="mt-4">
          {erro ? (
            <p className="text-sm text-destructive">⚠️ {erro}</p>
          ) : snapshots.length === 0 && carregando ? (
            <p className="text-sm text-muted-foreground">Carregando…</p>
          ) : snapshots.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhum snapshot importado ainda.</p>
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Data ref.</TableHead>
                      <TableHead>Ativo</TableHead>
                      <TableHead>Instituição</TableHead>
                      <TableHead className="text-right">Saldo líquido</TableHead>
                      <TableHead className="text-right">Rent. 12m</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {snapshots.map((s, i) => (
                      <TableRow key={`${s.position_key}-${s.data_referencia}-${i}`}>
                        <TableCell className="text-muted-foreground">{s.data_referencia}</TableCell>
                        <TableCell>
                          {s.nome}
                          <span className="block text-xs text-muted-foreground">{s.tipo}</span>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{s.instituicao}</TableCell>
                        <TableCell className="text-right">{formatBRL(s.saldo_liquido)}</TableCell>
                        <TableCell className="text-right">
                          {s.rentabilidade_12m_pct !== null ? formatPct(s.rentabilidade_12m_pct, 2) : "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                Mostrando {snapshots.length} de {total} snapshots.
              </p>
              {temMais && (
                <button
                  type="button"
                  onClick={() => carregarPagina(snapshots.length)}
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

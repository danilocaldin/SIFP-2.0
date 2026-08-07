"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { excluirPatrimonio } from "@/lib/api";
import { formatBRL, formatPct } from "@/lib/format";
import type { AssetPosition } from "@/lib/types";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export function PatrimonioAssetsTable({ assets }: { assets: AssetPosition[] }) {
  const router = useRouter();
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete(asset: AssetPosition) {
    if (!window.confirm(`Excluir o ativo "${asset.nome}" (${asset.data_referencia})? Essa ação não pode ser desfeita.`)) {
      return;
    }
    setDeletingKey(asset.position_key);
    setError(null);
    try {
      await excluirPatrimonio(asset.position_key);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido.");
    } finally {
      setDeletingKey(null);
    }
  }

  return (
    <div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Ativo</TableHead>
            <TableHead>Instituição</TableHead>
            <TableHead>Data ref.</TableHead>
            <TableHead className="text-right">Saldo líquido</TableHead>
            <TableHead className="text-right">Rent. 12m</TableHead>
            <TableHead className="text-right">Benchmark</TableHead>
            <TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {assets.map((a) => (
            <TableRow key={a.position_key}>
              <TableCell>
                {a.nome}
                <span className="block text-xs text-muted-foreground">{a.tipo}</span>
              </TableCell>
              <TableCell className="text-muted-foreground">{a.instituicao}</TableCell>
              <TableCell className="text-muted-foreground">{a.data_referencia}</TableCell>
              <TableCell className="text-right">{formatBRL(a.saldo_liquido)}</TableCell>
              <TableCell className="text-right">
                {a.rentabilidade_12m_pct !== null ? formatPct(a.rentabilidade_12m_pct, 2) : "—"}
              </TableCell>
              <TableCell className="text-right text-muted-foreground">
                {a.benchmark && a.benchmark_12m_pct !== null
                  ? `${a.benchmark} ${formatPct(a.benchmark_12m_pct, 2)}`
                  : "—"}
              </TableCell>
              <TableCell className="text-right">
                <button
                  type="button"
                  className="text-xs text-muted-foreground hover:text-red-600 dark:hover:text-red-400 disabled:opacity-50"
                  disabled={deletingKey === a.position_key}
                  onClick={() => handleDelete(a)}
                  title="Excluir ativo"
                >
                  {deletingKey === a.position_key ? "…" : "🗑️"}
                </button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {error && <p className="mt-2 text-sm text-red-600 dark:text-red-400">⚠️ {error}</p>}
    </div>
  );
}

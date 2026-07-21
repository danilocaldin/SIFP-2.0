"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { aplicarCategoriaEmLote } from "@/lib/api";
import { Button } from "@/components/ui/button";
import type { RevisaoLotePendente } from "@/lib/types";

export function RevisaoLote({
  pendentes,
  categorias,
}: {
  pendentes: RevisaoLotePendente[];
  categorias: string[];
}) {
  const router = useRouter();
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [busyDesc, setBusyDesc] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleApply(descricao: string) {
    const categoria = selected[descricao] ?? categorias[0];
    setBusyDesc(descricao);
    setError(null);
    try {
      const result = await aplicarCategoriaEmLote(descricao, categoria);
      setMessage(
        `${result.atualizadas} transação(ões) de "${descricao}" -> ${categoria}. ${result.mensagem_treino}`
      );
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido.");
    } finally {
      setBusyDesc(null);
    }
  }

  if (pendentes.length === 0) return null;

  return (
    <div className="space-y-3 rounded-lg border border-border p-4">
      <div>
        <h2 className="text-sm font-medium">🏪 Categorizar estabelecimentos pendentes em lote</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Cada linha agrupa todas as transações pendentes com a mesma descrição. Escolha a
          categoria e clique em Aplicar — resolve todas de uma vez.
        </p>
      </div>
      <div className="space-y-2">
        {pendentes.map((p) => (
          <div key={p.descricao} className="flex items-center gap-2">
            <span className="flex-1 text-sm">
              <span className="font-medium">{p.descricao}</span>{" "}
              <span className="text-muted-foreground">({p.quantidade}x)</span>
            </span>
            <select
              className="rounded border border-border bg-background px-2 py-1 text-sm"
              value={selected[p.descricao] ?? categorias[0]}
              onChange={(e) => setSelected((prev) => ({ ...prev, [p.descricao]: e.target.value }))}
            >
              {categorias.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <Button size="sm" disabled={busyDesc === p.descricao} onClick={() => handleApply(p.descricao)}>
              {busyDesc === p.descricao ? "Aplicando…" : "Aplicar"}
            </Button>
          </div>
        ))}
      </div>
      {message && <p className="text-sm text-emerald-600">✅ {message}</p>}
      {error && <p className="text-sm text-red-500">⚠️ {error}</p>}
    </div>
  );
}

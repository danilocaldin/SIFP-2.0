"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { confirmarRevisao, retreinarModelo } from "@/lib/api";
import { formatBRL } from "@/lib/format";
import type { RevisaoTransaction } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

export function RevisaoTable({
  transactions,
  categorias,
  categoriaNaoCategorizada,
}: {
  transactions: RevisaoTransaction[];
  categorias: string[];
  categoriaNaoCategorizada: string;
}) {
  const router = useRouter();
  const [onlyPending, setOnlyPending] = useState(false);
  const [lowConfidence, setLowConfidence] = useState(false);
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const visible = useMemo(() => {
    return transactions.filter((tx) => {
      if (onlyPending && tx.category !== categoriaNaoCategorizada) return false;
      if (lowConfidence && tx.confidence >= 0.6) return false;
      return true;
    });
  }, [transactions, onlyPending, lowConfidence, categoriaNaoCategorizada]);

  function handleCategoryChange(txHash: string, category: string) {
    setOverrides((prev) => ({ ...prev, [txHash]: category }));
  }

  async function handleConfirm() {
    setSaving(true);
    setError(null);
    try {
      const updates = visible.map((tx) => ({
        tx_hash: tx.tx_hash,
        category: overrides[tx.tx_hash] ?? tx.category,
      }));
      const result = await confirmarRevisao(updates);
      const pendingNote =
        result.ainda_pendentes > 0 ? ` ${result.ainda_pendentes} continuam pendentes.` : "";
      setMessage(`${result.confirmadas} transação(ões) confirmada(s).${pendingNote} ${result.mensagem_treino}`);
      setOverrides({});
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido.");
    } finally {
      setSaving(false);
    }
  }

  async function handleRetrain() {
    setError(null);
    try {
      const result = await retreinarModelo();
      setMessage(result.mensagem);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido.");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={onlyPending}
            onChange={(e) => setOnlyPending(e.target.checked)}
          />
          Mostrar apenas &quot;{categoriaNaoCategorizada}&quot;
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={lowConfidence}
            onChange={(e) => setLowConfidence(e.target.checked)}
          />
          Mostrar apenas baixa confiança (&lt;0.6)
        </label>
        <span className="text-sm text-muted-foreground">
          {visible.length} de {transactions.length} transações
        </span>
      </div>

      <p className="text-xs text-muted-foreground">
        Altere a categoria diretamente na coluna Categoria. Clique em Salvar para confirmar as
        linhas visíveis com a categoria escolhida (mesmo as que você não mudou — revisar e manter
        também é uma confirmação) e re-treinar o modelo. Linhas que continuarem como &quot;
        {categoriaNaoCategorizada}&quot; não são marcadas como confirmadas — seguem pendentes.
      </p>

      <div className="max-h-[600px] overflow-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-background">
            <tr className="border-b border-border text-left text-xs text-muted-foreground">
              <th className="p-2 font-medium">Data</th>
              <th className="p-2 font-medium">Descrição</th>
              <th className="p-2 text-right font-medium">Valor</th>
              <th className="p-2 font-medium">Categoria BTG</th>
              <th className="p-2 font-medium">Situação</th>
              <th className="p-2 font-medium">Categoria</th>
              <th className="p-2 font-medium">Confiança</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((tx) => (
              <tr key={tx.tx_hash} className="border-b border-border last:border-0">
                <td className="p-2 whitespace-nowrap text-muted-foreground">{tx.date}</td>
                <td className="p-2">{tx.description}</td>
                <td className="p-2 text-right whitespace-nowrap">{formatBRL(tx.value)}</td>
                <td className="p-2 text-muted-foreground">{tx.bank_category || "—"}</td>
                <td className="p-2 text-muted-foreground">{tx.situacao}</td>
                <td className="p-2">
                  <select
                    className="w-full min-w-[140px] rounded border border-border bg-background px-2 py-1 text-sm"
                    value={overrides[tx.tx_hash] ?? tx.category}
                    onChange={(e) => handleCategoryChange(tx.tx_hash, e.target.value)}
                  >
                    {categorias.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="w-24 p-2">
                  <Progress value={tx.confidence * 100} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button disabled={saving || visible.length === 0} onClick={handleConfirm}>
          {saving ? "Salvando…" : "💾 Salvar e confirmar linhas visíveis"}
        </Button>
        <Button variant="outline" onClick={handleRetrain}>
          🔁 Re-treinar modelo manualmente
        </Button>
      </div>
      {message && <p className="text-sm text-emerald-600">✅ {message}</p>}
      {error && <p className="text-sm text-red-500">⚠️ {error}</p>}
    </div>
  );
}

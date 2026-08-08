"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { confirmarRevisao, excluirTransacao, retreinarModelo } from "@/lib/api";
import { formatBRL } from "@/lib/format";
import type { RevisaoTransaction } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

// Achado real de auditoria: /api/revisao devolve TODAS as transações já
// importadas (sem paginação nem filtro de período no backend) -- já
// testado com ~750 linhas reais, e só cresce. Renderizar um <tr> com
// <select>+<Progress>+botão pra cada uma de uma vez é o risco real de
// travamento, não o payload em si (que já vem pronto do servidor). Em
// vez de mudar o contrato da API (quebraria "Salvar linhas visíveis",
// que precisa enxergar TODAS as linhas que passam no filtro, não só uma
// página), limita quantas linhas ficam de fato no DOM por vez.
const RENDER_PAGE_SIZE = 100;

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
  const [deletingHash, setDeletingHash] = useState<string | null>(null);
  const [renderLimit, setRenderLimit] = useState(RENDER_PAGE_SIZE);

  const visible = useMemo(() => {
    return transactions.filter((tx) => {
      if (onlyPending && tx.category !== categoriaNaoCategorizada) return false;
      if (lowConfidence && tx.confidence >= 0.6) return false;
      return true;
    });
  }, [transactions, onlyPending, lowConfidence, categoriaNaoCategorizada]);

  // "Salvar" continua processando TODAS as linhas de `visible` (o filtro
  // já escolhido pelo usuário), não só as renderizadas -- só o <tbody>
  // é limitado, pra não mudar o que o botão promete fazer.
  const renderizadas = visible.slice(0, renderLimit);
  const restantes = visible.length - renderizadas.length;

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

  async function handleDelete(tx: RevisaoTransaction) {
    if (!window.confirm(`Excluir a transação "${tx.description}" (${formatBRL(tx.value)})? Essa ação não pode ser desfeita.`)) {
      return;
    }
    setDeletingHash(tx.tx_hash);
    setError(null);
    try {
      await excluirTransacao(tx.tx_hash);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido.");
    } finally {
      setDeletingHash(null);
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
            onChange={(e) => {
              setOnlyPending(e.target.checked);
              setRenderLimit(RENDER_PAGE_SIZE);
            }}
          />
          Mostrar apenas &quot;{categoriaNaoCategorizada}&quot;
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={lowConfidence}
            onChange={(e) => {
              setLowConfidence(e.target.checked);
              setRenderLimit(RENDER_PAGE_SIZE);
            }}
          />
          Mostrar apenas baixa confiança (&lt;0.6)
        </label>
        <span className="text-sm text-muted-foreground">
          Exibindo {renderizadas.length} de {visible.length} filtradas ({transactions.length} no total)
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
              <th className="p-2 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {renderizadas.map((tx) => (
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
                <td className="p-2 text-right">
                  <button
                    type="button"
                    className="text-xs text-muted-foreground hover:text-red-700 dark:hover:text-red-400 disabled:opacity-50"
                    disabled={deletingHash === tx.tx_hash}
                    onClick={() => handleDelete(tx)}
                    title="Excluir transação"
                    aria-label={`Excluir transação: ${tx.description}`}
                  >
                    {deletingHash === tx.tx_hash ? "…" : "🗑️"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {restantes > 0 && (
        <button
          type="button"
          onClick={() => setRenderLimit((n) => n + RENDER_PAGE_SIZE)}
          className="text-xs font-medium text-foreground hover:underline"
        >
          Mostrar mais {Math.min(RENDER_PAGE_SIZE, restantes)} ({restantes} restantes)
        </button>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button disabled={saving || visible.length === 0} onClick={handleConfirm}>
          {saving ? "Salvando…" : "💾 Salvar e confirmar linhas visíveis"}
        </Button>
        <Button variant="outline" onClick={handleRetrain}>
          🔁 Re-treinar modelo manualmente
        </Button>
      </div>
      {message && <p className="text-sm text-emerald-700 dark:text-emerald-400">✅ {message}</p>}
      {error && <p className="text-sm text-red-700 dark:text-red-400">⚠️ {error}</p>}
    </div>
  );
}

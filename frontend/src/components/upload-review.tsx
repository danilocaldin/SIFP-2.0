"use client";

import { useState } from "react";
import { confirmarRevisao } from "@/lib/api";
import { formatBRL } from "@/lib/format";
import type { RevisaoPendenteItem } from "@/lib/types";
import { Button } from "@/components/ui/button";

export function UploadReview({
  items,
  categorias,
  onDone,
}: {
  items: RevisaoPendenteItem[];
  categorias: string[];
  onDone: (result: { confirmadas: number; puladas: number }) => void;
}) {
  const [index, setIndex] = useState(0);
  const [category, setCategory] = useState(items[0].category);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const current = items[index];
  const isLast = index === items.length - 1;

  function handleNext(answer: string | null) {
    const nextAnswers = { ...answers };
    if (answer) nextAnswers[current.tx_hash] = answer;
    setAnswers(nextAnswers);

    if (isLast) {
      void submit(nextAnswers);
    } else {
      const next = items[index + 1];
      setIndex(index + 1);
      setCategory(next.category);
    }
  }

  async function submit(finalAnswers: Record<string, string>) {
    setSubmitting(true);
    setError(null);
    const updates = Object.entries(finalAnswers).map(([tx_hash, cat]) => ({
      tx_hash,
      category: cat,
    }));
    try {
      let confirmadas = 0;
      if (updates.length > 0) {
        const result = await confirmarRevisao(updates);
        confirmadas = result.confirmadas;
      }
      onDone({ confirmadas, puladas: items.length - updates.length });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido.");
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-4 rounded-lg border border-amber-300 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/30">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">
          {index + 1} de {items.length}
        </span>
        <span className="text-xs font-medium">
          {current.is_transfer ? "↔️ Transferência" : "🏪 Novo estabelecimento"}
        </span>
      </div>

      <div>
        <p className="text-sm font-medium">{current.description}</p>
        <p className="text-sm text-muted-foreground">
          {current.date} · {formatBRL(current.value)}
        </p>
      </div>

      <p className="text-sm">
        {current.is_transfer
          ? "Essa transferência é referente a quê?"
          : "Que categoria é esse gasto?"}
      </p>

      <select
        className="w-full rounded border border-border bg-background px-2 py-1 text-sm"
        value={category}
        onChange={(e) => setCategory(e.target.value)}
      >
        {categorias.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>

      <div className="flex gap-2">
        <Button size="sm" disabled={submitting} onClick={() => handleNext(category)}>
          {isLast ? (submitting ? "Salvando…" : "Confirmar") : "Confirmar e próxima"}
        </Button>
        <Button size="sm" variant="outline" disabled={submitting} onClick={() => handleNext(null)}>
          {isLast ? "Pular e finalizar" : "Pular"}
        </Button>
      </div>
      {error && <p className="text-sm text-red-500">⚠️ {error}</p>}
    </div>
  );
}

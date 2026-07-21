"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { atualizarProgressoMeta, criarMeta, excluirMeta } from "@/lib/api";
import { formatBRL } from "@/lib/format";
import type { Goal } from "@/lib/types";

export function GoalsSection({ goals }: { goals: Goal[] }) {
  const router = useRouter();
  const [nome, setNome] = useState("");
  const [valorNecessario, setValorNecessario] = useState("");
  const [prazo, setPrazo] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const valor = Number(valorNecessario);
    if (!nome || !valor || valor <= 0 || !prazo) {
      setError("Preencha o nome, um valor maior que zero e o prazo.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await criarMeta(nome, valor, prazo);
      setNome("");
      setValorNecessario("");
      setPrazo("");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <h2 className="mb-3 text-sm font-medium text-muted-foreground">🏁 Metas financeiras</h2>

      <form onSubmit={handleSubmit} className="space-y-2">
        <Input
          placeholder="Nome da meta (ex: Reserva de emergência)"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
        />
        <Input
          type="number"
          min="0"
          step="0.01"
          placeholder="Valor necessário (R$)"
          value={valorNecessario}
          onChange={(e) => setValorNecessario(e.target.value)}
        />
        <Input type="date" value={prazo} onChange={(e) => setPrazo(e.target.value)} />
        <Button type="submit" disabled={saving}>
          {saving ? "Criando…" : "Criar meta"}
        </Button>
        {error && <p className="text-sm text-red-500">{error}</p>}
      </form>

      <div className="mt-6 space-y-4">
        {goals.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhuma meta cadastrada ainda.</p>
        ) : (
          goals.map((g) => <GoalRow key={g.id} goal={g} />)
        )}
      </div>
    </div>
  );
}

function GoalRow({ goal }: { goal: Goal }) {
  const router = useRouter();
  const [valor, setValor] = useState(String(goal.valor_acumulado));
  const [busy, setBusy] = useState(false);

  const progresso =
    goal.valor_necessario > 0
      ? Math.min((goal.valor_acumulado / goal.valor_necessario) * 100, 100)
      : 0;

  async function handleSave() {
    setBusy(true);
    try {
      await atualizarProgressoMeta(goal.id, Number(valor) || 0);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    setBusy(true);
    try {
      await excluirMeta(goal.id);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2 border-t border-border pt-4 first:border-t-0 first:pt-0">
      <p className="text-sm">
        <span className="font-medium">{goal.nome}</span> — {formatBRL(goal.valor_acumulado)} /{" "}
        {formatBRL(goal.valor_necessario)} ({progresso.toFixed(0)}%) — prazo {goal.prazo}
      </p>
      <Progress value={progresso} />
      <div className="flex gap-2">
        <Input
          type="number"
          min="0"
          step="0.01"
          value={valor}
          onChange={(e) => setValor(e.target.value)}
          className="max-w-[160px]"
        />
        <Button size="sm" variant="outline" disabled={busy} onClick={handleSave}>
          Salvar
        </Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={handleDelete}>
          Excluir
        </Button>
      </div>
    </div>
  );
}

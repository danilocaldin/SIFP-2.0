"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { criarLimite, removerLimite } from "@/lib/api";
import { formatBRL } from "@/lib/format";
import type { OrcamentoData } from "@/lib/types";

export function BudgetSection({ data }: { data: OrcamentoData }) {
  const router = useRouter();
  const [categoria, setCategoria] = useState(data.categorias[0] ?? "");
  const [valor, setValor] = useState<string>(() => {
    const s = data.sugestoes[data.categorias[0] ?? ""];
    return s ? s.toFixed(2) : "";
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sugestao = data.sugestoes[categoria];

  function handleCategoriaChange(value: string | null) {
    if (!value) return;
    setCategoria(value);
    const s = data.sugestoes[value];
    setValor(s ? s.toFixed(2) : "");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const numero = Number(valor);
    if (!numero || numero <= 0) {
      setError("Informe um valor maior que zero.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await criarLimite(categoria, numero);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido.");
    } finally {
      setSaving(false);
    }
  }

  async function handleRemove(category: string) {
    try {
      await removerLimite(category);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido.");
    }
  }

  return (
    <div>
      <h2 className="mb-3 text-sm font-medium text-muted-foreground">🎯 Limite por categoria</h2>

      <form onSubmit={handleSubmit} className="space-y-2">
        <Select value={categoria} onValueChange={handleCategoriaChange}>
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {data.categorias.map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {sugestao !== undefined && (
          <p className="text-xs text-muted-foreground">
            💡 Você gastou em média {formatBRL(sugestao)}/mês nessa categoria nos últimos meses —
            usamos como ponto de partida, ajuste se quiser.
          </p>
        )}

        <div className="flex gap-2">
          <Input
            type="number"
            min="0"
            step="0.01"
            placeholder="Limite mensal (R$)"
            value={valor}
            onChange={(e) => setValor(e.target.value)}
          />
          <Button type="submit" disabled={saving}>
            {saving ? "Salvando…" : "Salvar limite"}
          </Button>
        </div>
        {error && <p className="text-sm text-red-500">{error}</p>}
      </form>

      <div className="mt-6 space-y-4">
        {data.limites.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhum limite definido ainda.</p>
        ) : (
          data.limites.map((l) => {
            const pct = l.limite_mensal > 0 ? Math.min((l.gasto_atual / l.limite_mensal) * 100, 100) : 0;
            return (
              <div key={l.category} className="space-y-1">
                <div className="flex items-center justify-between">
                  <p className="text-sm">
                    <span className="font-medium">{l.category}</span> — {formatBRL(l.gasto_atual)} /{" "}
                    {formatBRL(l.limite_mensal)}
                  </p>
                  <button
                    onClick={() => handleRemove(l.category)}
                    className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
                  >
                    Remover
                  </button>
                </div>
                <Progress value={pct} />
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { CategoryBarChart } from "@/components/charts/category-bar-chart";
import { getDashboardCategoria } from "@/lib/api";
import { formatBRL } from "@/lib/format";
import type { CategoryBreakdown, CategoryTransaction } from "@/lib/types";

export function CategoryBreakdownSection({
  data,
  month,
}: {
  data: CategoryBreakdown[];
  month: string | null;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [transacoes, setTransacoes] = useState<CategoryTransaction[]>([]);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function handleCategoryClick(categoria: string) {
    if (selected === categoria) {
      setSelected(null);
      return;
    }
    setSelected(categoria);
    setCarregando(true);
    setErro(null);
    try {
      setTransacoes(await getDashboardCategoria(categoria, month));
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro desconhecido.");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <div>
      <CategoryBarChart data={data} selected={selected} onCategoryClick={handleCategoryClick} />

      {selected && (
        <div className="mt-3 rounded-lg border border-border">
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <p className="text-sm font-medium">{selected}</p>
            <button
              type="button"
              onClick={() => setSelected(null)}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Fechar
            </button>
          </div>
          <div className="max-h-64 overflow-auto">
            {carregando ? (
              <p className="p-3 text-sm text-muted-foreground">Carregando…</p>
            ) : erro ? (
              <p className="p-3 text-sm text-destructive">⚠️ {erro}</p>
            ) : transacoes.length === 0 ? (
              <p className="p-3 text-sm text-muted-foreground">
                Nenhuma transação encontrada nessa categoria.
              </p>
            ) : (
              <table className="w-full text-sm">
                <tbody>
                  {transacoes.map((t, i) => (
                    <tr key={`${t.date}-${t.description}-${i}`} className="border-b border-border last:border-0">
                      <td className="p-2 whitespace-nowrap text-muted-foreground">{t.date}</td>
                      <td className="p-2">{t.description}</td>
                      <td className="p-2 text-right whitespace-nowrap">{formatBRL(Math.abs(t.value))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

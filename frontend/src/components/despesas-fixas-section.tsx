"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  atualizarParcelaDespesaFixa,
  criarDespesaFixa,
  definirLimiteAlertaDespesasFixas,
  encerrarDespesaFixa,
  excluirDespesaFixa,
} from "@/lib/api";
import { formatBRL } from "@/lib/format";
import type { DespesaFixa, DespesasFixasData, TipoDespesaFixa } from "@/lib/types";

export function DespesasFixasSection({ data }: { data: DespesasFixasData }) {
  return (
    <div className="space-y-10">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <SummaryCard label="Total mensal comprometido" value={formatBRL(data.total_mensal)} />
        <SummaryCard
          label="% da renda média"
          value={data.pct_comprometido !== null ? `${data.pct_comprometido.toFixed(0)}%` : "—"}
        />
        <SummaryCard
          label="Margem mensal livre"
          value={data.margem_mensal !== null ? formatBRL(data.margem_mensal) : "—"}
        />
      </div>

      <div className="grid grid-cols-1 gap-10 lg:grid-cols-2">
        <div className="space-y-8">
          <NovaDespesaForm categorias={data.categorias} />
          <LimiteAlertaForm limiteAtual={data.limite_alerta_pct} />
        </div>

        <div>
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">📋 Despesas ativas</h2>
          {data.despesas.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhuma despesa fixa cadastrada ainda.</p>
          ) : (
            <div className="space-y-4">
              {data.despesas.map((d) => (
                <DespesaRow key={d.id} despesa={d} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold">{value}</p>
    </div>
  );
}

function NovaDespesaForm({ categorias }: { categorias: string[] }) {
  const router = useRouter();
  const [nome, setNome] = useState("");
  const [categoria, setCategoria] = useState(categorias[0] ?? "");
  const [valorMensal, setValorMensal] = useState("");
  const [tipo, setTipo] = useState<TipoDespesaFixa>("recorrente");
  const [dataInicio, setDataInicio] = useState(() => new Date().toISOString().slice(0, 10));
  const [parcelaAtual, setParcelaAtual] = useState("1");
  const [parcelasTotais, setParcelasTotais] = useState("12");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const valor = Number(valorMensal);
    if (!nome || !valor || valor <= 0) {
      setError("Preencha o nome e um valor maior que zero.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await criarDespesaFixa({
        nome,
        categoria,
        valor_mensal: valor,
        tipo,
        data_inicio: dataInicio,
        ...(tipo === "parcelada"
          ? { parcela_atual: Number(parcelaAtual) || 1, parcelas_totais: Number(parcelasTotais) || 1 }
          : {}),
      });
      setNome("");
      setValorMensal("");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <h2 className="mb-3 text-sm font-medium text-muted-foreground">➕ Nova despesa fixa</h2>
      <form onSubmit={handleSubmit} className="space-y-2">
        <Input
          placeholder="Nome (ex: Plano de saúde, Psicóloga, Notebook parcelado)"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
        />
        <Select value={categoria} onValueChange={(v) => v && setCategoria(v)}>
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {categorias.map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          type="number"
          min="0"
          step="0.01"
          placeholder="Valor mensal (R$)"
          value={valorMensal}
          onChange={(e) => setValorMensal(e.target.value)}
        />
        <Select value={tipo} onValueChange={(v) => v && setTipo(v as TipoDespesaFixa)}>
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="recorrente">Recorrente (sem fim definido)</SelectItem>
            <SelectItem value="parcelada">Parcelada (tem fim)</SelectItem>
          </SelectContent>
        </Select>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="data-inicio-despesa-fixa" className="text-xs text-muted-foreground">
            Início
          </Label>
          <Input
            id="data-inicio-despesa-fixa"
            type="date"
            value={dataInicio}
            onChange={(e) => setDataInicio(e.target.value)}
          />
        </div>
        {tipo === "parcelada" && (
          <div className="flex gap-2">
            <Input
              type="number"
              min="1"
              step="1"
              placeholder="Parcela atual"
              value={parcelaAtual}
              onChange={(e) => setParcelaAtual(e.target.value)}
            />
            <Input
              type="number"
              min="1"
              step="1"
              placeholder="Total de parcelas"
              value={parcelasTotais}
              onChange={(e) => setParcelasTotais(e.target.value)}
            />
          </div>
        )}
        <Button type="submit" disabled={saving}>
          {saving ? "Salvando…" : "Salvar despesa fixa"}
        </Button>
        {error && <p className="text-sm text-red-500">{error}</p>}
      </form>
    </div>
  );
}

function LimiteAlertaForm({ limiteAtual }: { limiteAtual: number | null }) {
  const router = useRouter();
  const [pct, setPct] = useState(String(limiteAtual ?? 30));
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const valor = Number(pct);
    if (!valor || valor <= 0) return;
    setSaving(true);
    try {
      await definirLimiteAlertaDespesasFixas(valor);
      router.refresh();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <h2 className="mb-1 text-sm font-medium text-muted-foreground">⚠️ Limite de alerta</h2>
      <p className="mb-3 text-xs text-muted-foreground">
        A partir de que % da sua renda média mensal comprometida com despesas fixas o Sifra deve te
        avisar? Fica a seu critério.
      </p>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <Input type="number" min="0" max="100" step="5" value={pct} onChange={(e) => setPct(e.target.value)} />
        <Button type="submit" variant="outline" disabled={saving}>
          {saving ? "Salvando…" : "Salvar limite"}
        </Button>
      </form>
    </div>
  );
}

function DespesaRow({ despesa }: { despesa: DespesaFixa }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  const progresso =
    despesa.tipo === "parcelada" && despesa.parcelas_totais
      ? Math.min(((despesa.parcela_atual ?? 0) / despesa.parcelas_totais) * 100, 100)
      : null;

  async function handleAvancarParcela() {
    if (!despesa.parcela_atual) return;
    setBusy(true);
    try {
      await atualizarParcelaDespesaFixa(despesa.id, despesa.parcela_atual + 1);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  async function handleEncerrar() {
    setBusy(true);
    try {
      await encerrarDespesaFixa(despesa.id);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  async function handleExcluir() {
    setBusy(true);
    try {
      await excluirDespesaFixa(despesa.id);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2 border-t border-border pt-4 first:border-t-0 first:pt-0">
      <p className="text-sm">
        <span className="font-medium">{despesa.nome}</span> — {formatBRL(despesa.valor_mensal)}/mês (
        {despesa.categoria})
      </p>
      {progresso !== null ? (
        <>
          <Progress value={progresso} />
          <p className="text-xs text-muted-foreground">
            Parcela {despesa.parcela_atual} de {despesa.parcelas_totais}
          </p>
        </>
      ) : (
        <p className="text-xs text-muted-foreground">Recorrente, sem fim definido.</p>
      )}
      <div className="flex gap-2">
        {progresso !== null && (
          <Button size="sm" variant="outline" disabled={busy} onClick={handleAvancarParcela}>
            Avançar parcela
          </Button>
        )}
        <Button size="sm" variant="outline" disabled={busy} onClick={handleEncerrar}>
          Encerrar
        </Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={handleExcluir}>
          Excluir
        </Button>
      </div>
    </div>
  );
}

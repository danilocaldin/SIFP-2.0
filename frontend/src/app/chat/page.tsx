"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { enviarMensagemChat } from "@/lib/api";
import type { ChatMensagem } from "@/lib/types";

const SUGESTOES = [
  "Quanto gastei com mercado nos últimos 3 meses?",
  "Qual foi meu maior gasto do mês passado?",
  "Como está meu patrimônio hoje?",
];

export default function ChatPage() {
  const [mensagens, setMensagens] = useState<ChatMensagem[]>([]);
  const [input, setInput] = useState("");
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function enviar(texto: string) {
    const pergunta = texto.trim();
    if (!pergunta || carregando) return;

    const novasMensagens: ChatMensagem[] = [...mensagens, { role: "user", content: pergunta }];
    setMensagens(novasMensagens);
    setInput("");
    setErro(null);
    setCarregando(true);

    try {
      const { resposta } = await enviarMensagemChat(novasMensagens);
      setMensagens([...novasMensagens, { role: "assistant", content: resposta }]);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro desconhecido.");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-6 py-12 sm:py-16">
      <p className="text-sm font-medium text-muted-foreground">Pergunte sobre suas finanças</p>
      <h1 className="mt-1 text-xl font-medium">Chat</h1>

      {mensagens.length === 0 && (
        <div className="mt-6 space-y-3">
          <p className="text-sm text-muted-foreground">
            Pergunte algo sobre suas transações, gastos por categoria ou patrimônio — as
            respostas vêm sempre dos seus dados reais, nunca de estimativas.
          </p>
          <div className="flex flex-wrap gap-2">
            {SUGESTOES.map((s) => (
              <button
                key={s}
                onClick={() => enviar(s)}
                className="rounded-full border border-border px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="mt-6 flex-1 space-y-4">
        {mensagens.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
            <div
              className={
                m.role === "user"
                  ? "max-w-[80%] rounded-2xl bg-foreground px-4 py-2 text-sm text-background"
                  : "max-w-[80%] rounded-2xl bg-muted px-4 py-2 text-sm"
              }
            >
              {m.content}
            </div>
          </div>
        ))}
        {carregando && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-2xl bg-muted px-4 py-2 text-sm text-muted-foreground">
              Pensando…
            </div>
          </div>
        )}
      </div>

      {erro && (
        <Card className="mt-4">
          <CardContent>
            <p className="text-sm text-red-500">⚠️ {erro}</p>
          </CardContent>
        </Card>
      )}

      <form
        className="mt-6 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          enviar(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Pergunte algo sobre suas finanças…"
          disabled={carregando}
          className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-foreground"
        />
        <Button type="submit" disabled={carregando || !input.trim()}>
          Enviar
        </Button>
      </form>
    </main>
  );
}

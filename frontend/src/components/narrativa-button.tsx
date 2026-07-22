"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { gerarNarrativa } from "@/lib/api";

type Status =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "success"; texto: string }
  | { kind: "error"; message: string };

export function NarrativaButton() {
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  async function handleClick() {
    setStatus({ kind: "loading" });
    try {
      const { texto } = await gerarNarrativa();
      setStatus({ kind: "success", texto });
    } catch (err) {
      setStatus({
        kind: "error",
        message: err instanceof Error ? err.message : "Erro desconhecido.",
      });
    }
  }

  return (
    <div className="mt-8 space-y-2">
      <Button
        variant="outline"
        size="sm"
        disabled={status.kind === "loading"}
        onClick={handleClick}
      >
        {status.kind === "loading" ? "Gerando…" : "🤖 Explicar este mês em linguagem natural"}
      </Button>

      {status.kind === "success" && (
        <Card>
          <CardContent>
            <p className="text-sm leading-relaxed">{status.texto}</p>
          </CardContent>
        </Card>
      )}

      {status.kind === "error" && (
        <p className="text-sm text-red-500">⚠️ {status.message}</p>
      )}
    </div>
  );
}

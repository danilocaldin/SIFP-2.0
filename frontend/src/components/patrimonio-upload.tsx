"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { PUBLIC_API_URL } from "@/lib/api";

type Status = { kind: "idle" } | { kind: "loading" } | { kind: "success"; message: string } | { kind: "error"; message: string };

export function PatrimonioUpload() {
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setStatus({ kind: "loading" });
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${PUBLIC_API_URL}/api/patrimonio/import`, {
        method: "POST",
        body: formData,
      });
      const body = await res.json();
      if (!res.ok) {
        throw new Error(body.detail ?? "Falha ao importar o extrato.");
      }
      setStatus({
        kind: "success",
        message: `${body.inserted} posição(ões) importada(s)/atualizada(s). Reimportar o mesmo extrato atualiza o snapshot da data em vez de duplicar.`,
      });
      router.refresh();
    } catch (err) {
      setStatus({ kind: "error", message: err instanceof Error ? err.message : "Erro desconhecido." });
    } finally {
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3">
        <Button
          variant="outline"
          size="sm"
          disabled={status.kind === "loading"}
          onClick={() => inputRef.current?.click()}
        >
          {status.kind === "loading" ? "Importando…" : "Importar extrato (PDF)"}
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={handleFileChange}
        />
      </div>
      {status.kind === "success" && (
        <p className="text-sm text-emerald-600">✅ {status.message}</p>
      )}
      {status.kind === "error" && <p className="text-sm text-red-500">⚠️ {status.message}</p>}
    </div>
  );
}

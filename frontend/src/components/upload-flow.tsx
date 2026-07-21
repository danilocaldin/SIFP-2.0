"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { previewUpload, persistUpload } from "@/lib/api";
import { formatBRL } from "@/lib/format";
import type { UploadPersistSummary, UploadPreview } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type Status =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "previewed"; preview: UploadPreview }
  | { kind: "persisting"; preview: UploadPreview }
  | { kind: "done"; summary: UploadPersistSummary }
  | { kind: "error"; message: string };

export function UploadFlow() {
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const fileRef = useRef<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    fileRef.current = file;
    setStatus({ kind: "loading" });
    try {
      const preview = await previewUpload(file);
      setStatus({ kind: "previewed", preview });
    } catch (err) {
      setStatus({ kind: "error", message: err instanceof Error ? err.message : "Erro desconhecido." });
    }
  }

  async function handleConfirm(preview: UploadPreview) {
    const file = fileRef.current;
    if (!file) return;
    setStatus({ kind: "persisting", preview });
    try {
      const summary = await persistUpload(file);
      setStatus({ kind: "done", summary });
      router.refresh();
    } catch (err) {
      setStatus({ kind: "error", message: err instanceof Error ? err.message : "Erro desconhecido." });
    }
  }

  function handleReset() {
    fileRef.current = null;
    if (inputRef.current) inputRef.current.value = "";
    setStatus({ kind: "idle" });
  }

  return (
    <div className="space-y-4">
      {(status.kind === "idle" || status.kind === "error") && (
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => inputRef.current?.click()}>
            Selecionar arquivo (CSV, XLS ou XLSX)
          </Button>
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept=".csv,.xls,.xlsx"
        className="hidden"
        onChange={handleFileChange}
      />

      {status.kind === "loading" && <p className="text-sm text-muted-foreground">Lendo arquivo…</p>}

      {status.kind === "error" && <p className="text-sm text-red-500">⚠️ {status.message}</p>}

      {(status.kind === "previewed" || status.kind === "persisting") && (
        <div className="space-y-3">
          <p className="text-sm">
            Arquivo lido com sucesso: <span className="font-medium">{status.preview.count}</span>{" "}
            transação(ões) encontrada(s)
            {status.preview.balances_count > 0 && (
              <> e {status.preview.balances_count} saldo(s) diário(s)</>
            )}
            .
          </p>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Data</TableHead>
                <TableHead>Descrição</TableHead>
                <TableHead className="text-right">Valor</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {status.preview.preview.map((tx, i) => (
                <TableRow key={i}>
                  <TableCell className="text-muted-foreground">{tx.date}</TableCell>
                  <TableCell>{tx.description}</TableCell>
                  <TableCell className="text-right">{formatBRL(tx.value)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {status.preview.count > status.preview.preview.length && (
            <p className="text-xs text-muted-foreground">
              Mostrando as {status.preview.preview.length} primeiras — todas as{" "}
              {status.preview.count} serão importadas.
            </p>
          )}

          <div className="flex gap-2">
            <Button
              disabled={status.kind === "persisting"}
              onClick={() => handleConfirm(status.preview)}
            >
              {status.kind === "persisting" ? "Processando…" : "Processar e Categorizar"}
            </Button>
            <Button variant="outline" disabled={status.kind === "persisting"} onClick={handleReset}>
              Cancelar
            </Button>
          </div>
        </div>
      )}

      {status.kind === "done" && (
        <div className="space-y-3">
          <p className="text-sm text-emerald-600">
            ✅ {status.summary.inseridas} transação(ões) nova(s) importada(s).{" "}
            {status.summary.ignoradas_duplicadas} já existia(m) no banco e foram ignorada(s) (sem
            duplicidade).
            {status.summary.saldos_gravados > 0 && (
              <> {status.summary.saldos_gravados} saldo(s) diário(s) gravado(s).</>
            )}
          </p>
          <Button variant="outline" size="sm" onClick={handleReset}>
            Importar outro arquivo
          </Button>
        </div>
      )}
    </div>
  );
}

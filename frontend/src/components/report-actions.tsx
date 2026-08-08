"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { baixarRelatorioPdf } from "@/lib/api";

export function ReportActions({ reportText, month }: { reportText: string; month: string }) {
  const [copied, setCopied] = useState(false);
  const [gerandoPdf, setGerandoPdf] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function handleCopy() {
    await navigator.clipboard.writeText(reportText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleDownload() {
    const blob = new Blob([reportText], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `relatorio_sifp_${month}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleDownloadPdf() {
    setGerandoPdf(true);
    setErro(null);
    try {
      const blob = await baixarRelatorioPdf(month);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `relatorio_sifra_${month}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setErro("Não foi possível gerar o PDF. Tente novamente em instantes.");
    } finally {
      setGerandoPdf(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        <Button variant="outline" size="sm" onClick={handleCopy}>
          {copied ? "Copiado!" : "Copiar"}
        </Button>
        <Button variant="outline" size="sm" onClick={handleDownload}>
          Baixar (.txt)
        </Button>
        <Button size="sm" onClick={handleDownloadPdf} disabled={gerandoPdf}>
          {gerandoPdf ? "Gerando…" : "Baixar PDF"}
        </Button>
      </div>
      {erro && <p className="text-sm text-destructive">⚠️ {erro}</p>}
    </div>
  );
}

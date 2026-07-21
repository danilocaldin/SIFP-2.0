"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

export function ReportActions({ reportText, month }: { reportText: string; month: string }) {
  const [copied, setCopied] = useState(false);

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

  return (
    <div className="flex gap-2">
      <Button variant="outline" size="sm" onClick={handleCopy}>
        {copied ? "Copiado!" : "Copiar"}
      </Button>
      <Button variant="outline" size="sm" onClick={handleDownload}>
        Baixar (.txt)
      </Button>
    </div>
  );
}

"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="mx-auto flex min-h-[60vh] w-full max-w-md flex-col items-center justify-center gap-3 px-6 text-center">
      <h1 className="text-xl font-medium">Algo deu errado por aqui</h1>
      <p className="text-sm text-muted-foreground">
        Pode ser instabilidade momentânea da API — tente de novo em alguns segundos. Se persistir,
        os dados continuam salvos, só essa tela que não carregou.
      </p>
      <Button variant="outline" size="sm" onClick={reset}>
        Tentar de novo
      </Button>
    </main>
  );
}

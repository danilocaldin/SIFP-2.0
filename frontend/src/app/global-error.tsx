"use client";

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="pt-BR">
      <body className="flex min-h-screen items-center justify-center bg-background text-foreground">
        <main className="mx-auto flex w-full max-w-md flex-col items-center gap-3 px-6 text-center">
          <h1 className="text-xl font-medium">O SIFP não conseguiu carregar</h1>
          <p className="text-sm text-muted-foreground">
            Algo deu errado na aplicação inteira, não só numa tela. Tente recarregar a página.
          </p>
          <button
            onClick={reset}
            className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-muted"
          >
            Tentar de novo
          </button>
        </main>
      </body>
    </html>
  );
}

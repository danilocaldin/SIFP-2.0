import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-[60vh] w-full max-w-md flex-col items-center justify-center gap-3 px-6 text-center">
      <h1 className="text-xl font-medium">Essa página não existe</h1>
      <p className="text-sm text-muted-foreground">
        Confira o link ou{" "}
        <Link href="/" className="underline underline-offset-2 hover:text-foreground">
          volte pro Resumo
        </Link>
        .
      </p>
    </main>
  );
}

import { Skeleton } from "@/components/ui/skeleton";

// Estado de carregamento genérico pras rotas que buscam dado no
// servidor (Server Components async) -- achado real de auditoria:
// nenhuma rota tinha loading.tsx, então clicar num item da sidebar
// parecia travado até o servidor terminar de responder, sem feedback
// nenhum de que o clique funcionou. Não tenta imitar o layout exato de
// cada tela (não vale o custo de manutenção); só dá uma pista visível
// de "algo está carregando aqui" enquanto os dados chegam.
export function PageSkeleton({ maxWidth = "max-w-4xl" }: { maxWidth?: string }) {
  return (
    <main className={`mx-auto w-full ${maxWidth} flex-1 px-6 py-12 sm:py-16`}>
      <Skeleton className="h-4 w-24" />
      <Skeleton className="mt-2 h-7 w-64" />

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Skeleton className="h-20 rounded-lg" />
        <Skeleton className="h-20 rounded-lg" />
        <Skeleton className="h-20 rounded-lg" />
      </div>

      <Skeleton className="mt-10 h-64 rounded-lg" />
      <Skeleton className="mt-6 h-40 rounded-lg" />
    </main>
  );
}

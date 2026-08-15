"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { clienteVisualizadoNoNavegador, encerrarVisualizacaoCliente } from "@/lib/impersonation";

const SAAS_MODE = process.env.NEXT_PUBLIC_SAAS_MODE === "true";

// Sempre visível enquanto o cookie de impersonação existir (setado em
// /clientes) -- pra nunca ficar ambíguo de quem são os dados na tela. Lê
// o cookie no cliente (não via prop do layout) porque ele só existe
// depois de "Visualizar" ser clicado nessa mesma sessão de navegador.
export function ImpersonationBanner() {
  const router = useRouter();
  const pathname = usePathname();
  const [cliente, setCliente] = useState<{ id: string; email: string } | null>(null);

  useEffect(() => {
    // Depende de `pathname`: este componente vive no layout raiz, que NÃO
    // remonta em navegação client-side -- sem isso, o cookie só seria lido
    // uma vez (no primeiro carregamento da aba), e clicar em "Visualizar"
    // em /clientes (que navega pra /) nunca atualizaria o banner. Achado
    // real testando o fluxo no navegador, não hipotético.
    //
    // Promise.resolve().then() em vez de setCliente direto: document.cookie
    // só existe no cliente, então essa leitura tem que acontecer depois da
    // hidratação -- mesmo padrão de sidebar.tsx (satisfaz
    // react-hooks/set-state-in-effect sem atrasar nada visivelmente).
    Promise.resolve().then(() => setCliente(clienteVisualizadoNoNavegador()));
  }, [pathname]);

  if (!SAAS_MODE || !cliente) return null;

  function handleSair() {
    encerrarVisualizacaoCliente();
    setCliente(null);
    router.push("/");
    router.refresh();
  }

  return (
    <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 bg-amber-500/15 px-4 py-2 text-center text-sm text-amber-900 dark:bg-amber-500/10 dark:text-amber-300">
      <span>
        Visualizando como cliente: <strong>{cliente.email}</strong> — modo somente leitura.
      </span>
      <button
        type="button"
        onClick={handleSair}
        className="underline underline-offset-2 hover:no-underline"
      >
        Sair da visualização
      </button>
    </div>
  );
}

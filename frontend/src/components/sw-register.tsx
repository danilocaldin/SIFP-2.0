"use client";

import { useEffect } from "react";

// Registra o service worker mínimo (public/sw.js) — é a peça que falta
// pra instalabilidade em Chrome/Android; iOS Safari ignora e usa
// apple-icon + display:standalone diretamente via "Adicionar à Tela de Início".
export function ServiceWorkerRegister() {
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);

  return null;
}

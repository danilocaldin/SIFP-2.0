// Service worker deliberadamente mínimo: existe só pra satisfazer o
// requisito de instalabilidade do Chrome/Android (precisa de um handler
// de fetch registrado), sem cachear nada. Um app financeiro nunca deve
// mostrar dado desatualizado offline — cada resposta sempre vem da rede.
self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  // Navegação de página inteira (abrir uma URL, trocar de rota) fica de
  // fora de propósito: repassar esse tipo de Request pro fetch() dentro
  // do service worker é um bug conhecido do Chrome ("Failed to fetch"
  // intermitente) — não interceptar deixa o navegador navegar do jeito
  // normal, sem nenhuma mudança de comportamento visível (continua sem
  // cache, sempre busca da rede).
  if (event.request.mode === "navigate") {
    return;
  }
  event.respondWith(fetch(event.request));
});

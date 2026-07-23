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
  event.respondWith(fetch(event.request));
});

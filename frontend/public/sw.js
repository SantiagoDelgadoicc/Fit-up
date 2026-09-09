/*
 * Service worker minimo.
 *
 * Solo cachea el armazon de la aplicacion para que abra aunque el PC este
 * apagado o el WiFi falle (mitiga el punto debil de ADR-0001). Las peticiones
 * a /api NUNCA se cachean: mostrar un historial obsoleto como si fuera actual
 * seria peor que mostrar un error.
 */
const CACHE = "fitup-shell-v2";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) =>
      cache.addAll([
        "/",
        "/manifest.webmanifest",
        "/icon.svg",
        // El logo y las dos fuentes latinas van en el armazon: sin ellos, la
        // primera carga sin conexion enseñaria la app con la letra del sistema
        // y sin marca. Los subconjuntos latin-ext los cachea el propio `fetch`
        // si algun dia hacen falta.
        "/logo.png",
        "/fonts/inter-latin.woff2",
        "/fonts/outfit-latin.woff2",
      ]),
    ),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) => Promise.all(names.filter((n) => n !== CACHE).map((n) => caches.delete(n)))),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.pathname.startsWith("/api")) return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        void caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        return response;
      })
      .catch(() => caches.match(event.request).then((hit) => hit ?? caches.match("/"))),
  );
});

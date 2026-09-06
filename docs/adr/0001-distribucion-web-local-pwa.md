# ADR-0001 — Distribución: aplicación web local + PWA

**Estado:** Aceptada (2026-09-06) · **Reemplaza a:** D1

## Contexto
Fit-Up debe ser legible desde el móvil durante el entrenamiento y, a la vez, sus datos deben ser accesibles a un agente de IA que se ejecuta en el PC. Una app de escritorio cubre lo segundo pero no lo primero; una PWA puramente offline cubre lo primero pero deja los datos en el navegador del móvil, fuera del alcance del agente.

## Decisión
Un único proceso servidor en el PC expone **API HTTP + UI**. La UI es una **PWA** instalable, accesible desde el navegador del PC y desde el móvil en la misma red WiFi.

## Alternativas descartadas
- **App de escritorio (Tauri/Electron):** sin acceso desde el gimnasio; además obliga a coordinar el acceso concurrente a SQLite entre app y agente.
- **PWA pura offline (IndexedDB):** rompe el requisito de que un agente local pueda leer y analizar los datos; exigiría sincronización, con complejidad desproporcionada para un solo usuario.

## Consecuencias
- Una sola base de código sirve a UI y agente; cero sincronización.
- **El PC debe estar encendido** para usar la app desde el móvil. Se mitiga con caché offline de la PWA para modo lectura (consultar la rutina sin red).
- Al quedar el servidor expuesto en la LAN, el **token de acceso es obligatorio** y el binding debe ser explícito y configurable (`127.0.0.1` por defecto, IP de LAN de forma consciente).
- El registro offline desde el móvil (cola local + sincronización al volver) queda como mejora posterior, no como requisito de v1.

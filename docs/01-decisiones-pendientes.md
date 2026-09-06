# Decisiones pendientes de aprobación humana

Estado: **abiertas**. No se escribe código de aplicación hasta cerrar D1–D4.
Al resolver cada una se crea su ADR en `docs/adr/`.

---

## D1 — Forma de distribución de la aplicación 🔴 BLOQUEANTE

**Problema:** determina si puedes leer la rutina **desde el móvil mientras entrenas**, y cómo se conecta el agente de IA. Es la decisión más difícil de revertir: cambia el stack, el despliegue y el modelo de acceso.

**Opción A — App web local (servidor en el PC + PWA)**
Un proceso en el PC sirve API + UI. Se abre en el navegador del PC y, en la misma red WiFi, desde el móvil (`http://192.168.x.x:8000`).
- ✅ Móvil en el gimnasio de casa sin instalar nada; el agente de IA habla con el mismo proceso; una sola base de código; PWA instalable.
- ❌ El PC debe estar encendido; requiere token si se expone en LAN; en gimnasio externo (fuera de la WiFi) no hay acceso salvo caché offline de la PWA.
- ⚠️ Riesgo: exponer un puerto en la red doméstica. Mitigable con bind explícito + token.

**Opción B — App de escritorio (Tauri/Electron) + servidor MCP aparte**
Aplicación instalable en el PC; el agente accede por MCP a la misma BD.
- ✅ Sin puertos de red; arranque de un clic; sensación de app nativa; ficheros y BD locales sin fricción.
- ❌ **Solo funciona en el PC**: no puedes consultar la rutina en el gimnasio; hay que coordinar el acceso concurrente app↔agente a SQLite; empaquetado más complejo.

**Opción C — PWA pura offline (todo en el navegador, IndexedDB)**
- ✅ Funciona en el móvil siempre, incluso sin PC.
- ❌ **Rompe el requisito nº 8**: el agente en el PC no puede leer los datos (viven en el navegador del móvil); necesitarías sincronización → complejidad muy superior.

**Recomendación: A.**
Es la única que satisface a la vez "leer mientras entreno" y "agente local que lee y escribe", con una sola base de código y sin sincronización. La debilidad (PC encendido) se mitiga con caché offline de la PWA para el modo lectura.

**Impacto:** stack completo, despliegue, seguridad, integración con IA.
**Decisión requerida:** A, B o C.

---

## D2 — Stack tecnológico principal 🔴 BLOQUEANTE

**Problema:** el proyecto es de larga vida y de un solo desarrollador. La elección debe optimizar tu velocidad, no la moda.

**Opción A — Python (FastAPI) + SQLite, frontend React/TypeScript**
- ✅ OpenAPI generado automáticamente → contrato gratis para el agente de IA; SDK de MCP maduro en Python; la lógica de cálculo (progresión, ranking, métricas) es más cómoda de escribir y testear en Python; ecosistema de análisis a futuro.
- ❌ Dos lenguajes, dos toolchains; los tipos del dominio se definen dos veces (mitigable generando tipos TS desde OpenAPI).

**Opción B — Monorepo TypeScript (Fastify + SQLite + React)**
- ✅ Un solo lenguaje; esquemas Zod **compartidos** entre backend y frontend (una sola definición de dominio); un solo `npm install`.
- ❌ OpenAPI requiere trabajo extra; MCP en TS es viable pero con menos ejemplos; matemática/estadística menos ergonómica.

**Recomendación: A**, salvo que seas claramente más fuerte en TypeScript que en Python — en ese caso B, y no es una mala decisión.
Lo relevante es que **el dominio puro es portable en ambos casos**: la arquitectura no depende de esta elección.

**Impacto:** productividad diaria, integración con IA, esfuerzo de mantenimiento.
**Decisión requerida:** A o B (y dime tu lenguaje más fuerte).

---

## D3 — Qué representa el rango muscular 🔴 BLOQUEANTE

**Problema:** pediste explícitamente distinguir *cantidad de entrenamiento* de *desarrollo muscular*. La elección define si el ranking motiva o miente.

**Opción A — El rango = Desarrollo/Capacidad** (recomendada)
Lento, con trinquete, no se desploma al descansar. La Actividad reciente se muestra como halo secundario.
- ✅ Un rango que significa algo; no castiga el descanso; sube al progresar.
- ❌ Se mueve despacio: menos dopamina semanal.

**Opción B — El rango = Carga/Actividad reciente**
- ✅ Feedback inmediato: entrenas y sube.
- ❌ Baja en cuanto descansas una semana; mide esfuerzo, no capacidad; puede empujar a sobreentrenar por el color.

**Opción C — Dos rangos separados** (uno por métrica).
- ✅ Máxima honestidad. ❌ Duplica la UI y diluye la característica insignia.

**Sub-decisión (umbrales):** relativo a tu propia historia (llegas a Radiant en semanas) vs **absolutos anclados al peso corporal** (recomendado, aspiracional) vs híbrido.

**Recomendación: A + umbrales absolutos editables + bonus por progresión + suelo anti-decaimiento.**

**Impacto:** motivación a largo plazo, credibilidad del sistema, complejidad del cálculo.
**Decisión requerida:** A, B o C, y qué tipo de umbral.

---

## D4 — Permisos del agente de IA 🔴 BLOQUEANTE

**Opción A — Solo lectura + propuestas** (recomendada)
El agente nunca escribe directamente; genera propuestas que apruebas en la app.
- ✅ Imposible corromper datos; auditoría completa; mantienes control.
- ❌ Un paso manual por cada cambio.

**Opción B — Escritura directa con auditoría y deshacer**
- ✅ Automatización real. ❌ Un modelo confundido puede escribir historial falso; deshacer no siempre es evidente.

**Opción C — Mixto:** escritura directa en sesiones (`log_workout`), propuestas para rutinas.
- ✅ Equilibrio pragmático. ❌ Dos modelos mentales de permisos.

**Recomendación: A ahora, con la puerta abierta a C** cuando confíes en tu agente. El diseño lo soporta sin refactor: es un flag de scope.

**Impacto:** seguridad e integridad de los datos.
**Decisión requerida:** A, B o C.

---

## Decisiones menores — se aplican por defecto salvo que digas lo contrario

| # | Tema | Default propuesto |
|---|---|---|
| d5 | Planificación | Semana fija (lunes–domingo), esquema preparado para ciclos rotativos |
| d6 | Ventana de gracia antes de marcar 🔴 | 3 días |
| d7 | Series planificadas | Filas explícitas (3×15 = 3 filas), generadas por la UI |
| d8 | Unidades | Kilogramos |
| d9 | Base de datos | SQLite con migraciones versionadas |
| d10 | RIR/RPE por serie | Campo opcional presente desde F1 |
| d11 | Músculo sin ejercicios | Estado "Sin datos", no Iron |
| d12 | Sesión parcial | Estado `partial` soportado desde F1 |
| d13 | Backup | Copia diaria automática + export JSON manual |
| d14 | Tema | Oscuro por defecto |
| d15 | Fechas futuras | Prohibido registrar en el futuro |

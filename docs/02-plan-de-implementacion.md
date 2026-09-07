# Plan de implementación

Documento vivo. Se marca cada casilla al completar el hito y se actualiza la tabla de
estado. Cada fase termina en un incremento **usable**, no en una capa técnica a medias.

**Estado global:** F0–F4 completadas · siguiente F5

| Fase | Objetivo | Estado |
|---|---|---|
| [F0](#f0--fundamentos) | Base técnica: esquema, dominio, catálogo, CI | ✅ Completada |
| [F1](#f1--mvp-de-registro) | Registrar entrenamientos a diario | ✅ Completada |
| [F2](#f2--calendario-y-cumplimiento) | Ver adherencia en un calendario mensual | ✅ Completada |
| [F3](#f3--progresión) | Aplicar sobrecarga progresiva con un botón | ✅ Completada |
| [F4](#f4--métricas-y-ranking-muscular) | Mapa corporal con rangos Iron→Radiant | ✅ Completada |
| [F5](#f5--temporizador) | Descansos durante el entrenamiento | ⬜ Siguiente |
| [F6](#f6--agente-de-ia) | Contrato estable para el agente local | ⬜ |
| [F7](#f7--pulido) | Backups, offline, accesibilidad | ⬜ |

---

## F0 · Fundamentos

**Objetivo:** que exista una base sobre la que construir sin tener que rehacerla.
**Completada:** 2026-09-06

- [x] Decisiones estructurales cerradas en ADR (0001–0004)
- [x] Esquema SQL completo con las cuatro capas de datos (migración `0001_initial`)
- [x] Migrador con versionado y verificación de checksum
- [x] Conexión SQLite con WAL, `foreign_keys` y `busy_timeout`
- [x] Catálogo semilla: 18 músculos, 11 reglas, 58 ejercicios, 161 vínculos
- [x] Validación del catálogo (slugs, roles, `load_factor`, ciclos de variantes)
- [x] Dominio puro: `enums`, `models`, `metrics/load`, `compliance/day_state`
- [x] Motor de progresión con las 7 estrategias y sus guardas
- [x] Ranking v1: desarrollo, actividad, tiers, explicabilidad
- [x] 176 tests · 92 % de cobertura en `domain/`
- [x] CLI `fitup init` / `fitup check`
- [x] CI: lint, formato, tests, umbral de cobertura y arranque de extremo a extremo

**Aprendido en F0:** el suelo de decaimiento del ranking y la ventana de 180 días se
contradecían. Resuelto haciendo la frontera explícita: dentro de la ventana el rango decae
poco; fuera, vuelve a `SIN_DATOS` en lugar de afirmar una capacidad sin evidencia.

---

## F1 · MVP de registro

**Objetivo:** poder usar Fit-Up a diario.
**Completada:** 2026-09-06
**Criterio de aceptación:** registrar el entrenamiento de un martes desde el móvil el
domingo siguiente, en menos de 30 segundos. ✅ Verificado en la app real.

### Backend
- [x] Capa `application` con casos de uso puros de HTTP (reutilizables por el MCP de F6)
- [x] Repositorios SQLite que devuelven objetos de dominio, no filas
- [x] API FastAPI con OpenAPI: 24 endpoints
- [x] Registro **como planificado** en una sola llamada
- [x] Registro retroactivo usando la versión de rutina vigente **ese día**
- [x] Peso corporal: registro y consulta
- [x] Export JSON completo + backup diario automático *(M5, adelantado desde F7)*
- [x] Token de acceso y binding configurable (`127.0.0.1` por defecto, `--lan` para el móvil)
- [x] Cabecera `Idempotency-Key`: un reintento no duplica el entrenamiento

### Frontend
- [x] React + TypeScript + Vite, PWA instalable, tema oscuro
- [x] Tipos TS generados desde OpenAPI (una sola definición del contrato)
- [x] Pantalla **Hoy**: rutina del día + botón «✓ Hice esta rutina»
- [x] Sección «Pendientes de registrar» resoluble en un toque
- [x] Editor de rutinas con prescripción compacta (3×15) y calentamiento
- [x] Organización de la semana
- [x] Historial navegable con detalle por serie
- [x] Ajustes: peso corporal, ventana de gracia, token, export
- [x] Servida desde el mismo proceso que la API (ADR-0001)

### Decisiones aplicadas
- **RIR/RPE opcional por serie:** sí. Es la señal que hará segura la progresión de F3.
- **Estado `partial` visible:** sí, con su propio botón («La hice a medias»).

**Aprendido en F1** — cuatro fallos que encontraron los tests y la prueba en la app real:

1. `set_week` intentaba cerrar un tramo que empezaba ese mismo día, violando el CHECK
   del esquema. El orden correcto es borrar los tramos superados y solo después cerrar
   el anterior.
2. `with sqlite3.connect(...)` gestiona la transacción pero **no cierra** la conexión:
   cada copia de seguridad dejaba el fichero abierto.
3. Una conexión SQLite global rompe en el threadpool de FastAPI. Ahora se abre una por
   petición: sin estado compartido entre hilos y con transacciones aisladas.
4. El editor descartaba en silencio las series de calentamiento al guardar. Si el
   backend soporta algo, la UI debe poder producirlo y no destruirlo.

---

## F2 · Calendario y cumplimiento

**Objetivo:** ver de un vistazo qué se cumplió y qué no, sin que la app mienta sobre lo
que aún no has registrado.
**Completada:** 2026-09-07

- [x] `calendario(mes)` resolviendo los 7 estados del día
- [x] Cada día lleva qué rutina tocaba y, si la hay, la sesión registrada
- [x] Métrica de adherencia excluyendo `PENDING`
- [x] Vista mensual navegable, con **color + icono** (nunca solo color)
- [x] Detalle del día: planificado vs realizado, con acciones
- [x] Registro retroactivo desde el calendario, en un toque
- [x] Excepciones (descanso, lesión, viaje, movido) desde la UI
- [x] Ventana de gracia configurable en ajustes
- [x] Flechas ← → para cambiar de mes

**Rediseño para escritorio** ([ADR-0005](adr/0005-el-pc-es-la-superficie-principal.md)):
el PC es la superficie principal, no el móvil. Dos columnas en el calendario, ancho por
página, densidad mayor en pantalla ancha y navegación lateral con marca.

**Aprendido en F2** — dos fallos, y los dos dicen algo sobre cómo probar:

1. **La API rompía en el servidor real y los 42 tests con `TestClient` pasaban.** FastAPI
   resuelve la dependencia y ejecuta el endpoint en hilos distintos de su threadpool, y
   SQLite rechaza una conexión usada desde otro hilo. Corregido con
   `check_same_thread=False` —seguro porque cada petición abre y cierra la suya, en
   secuencia— y cubierto con un test contra un **uvicorn real**.
   La primera versión de ese test tampoco fallaba: hacía las peticiones en serie y el
   threadpool reutilizaba el hilo. Solo lanzándolas **en paralelo**, como hace la
   interfaz al abrir una pantalla, aparece el error. *Un test que no falla ante el fallo
   que dice cubrir no sirve*, así que se verificó reintroduciendo el bug a propósito.
2. **Un control que no hacía nada.** El selector de excepción aparecía en días marcados
   como "no la hice", pero en el dominio una sesión registrada manda sobre la excepción,
   así que elegir "lesión" no cambiaba el día. Resuelto sin tocar la regla del dominio:
   la UI retira ese registro y luego excusa el día, que es lo que pide quien elige
   "lesión".

## F3 · Progresión

**Objetivo:** el botón "Progresar" del enunciado, sin que pueda subir la dificultad de
forma irresponsable.
**Completada:** 2026-09-07
**Criterio de aceptación:** ver qué toca subir, entender por qué, aplicarlo y poder
volver atrás sin perder historial. ✅ Verificado en la app real.

- [x] `EvaluarProgresion` sobre todos los ejercicios de una rutina
- [x] `AplicarProgresion`: nueva versión + `progression_event`, transaccional
- [x] Deshacer una progresión (nueva versión que revierte; nunca se borra historia)
- [x] UI: badge "listo para progresar", preview del diff, confirmación
- [x] Mostrar `UNDETERMINED` con su motivo, sin ocultarlo
- [x] Editor de reglas por ejercicio
- [x] Deload sugerido tras regresiones *(M3)*
- [x] Cadena de variantes para calistenia en la UI *(M8)*
- [x] Aviso de progresiones disponibles en «Hoy» y en el listado de rutinas
- [x] Progresiones incluidas en el export JSON

Sin migraciones: `progression_event` estaba en el esquema desde F0 y el motor puro, con
sus siete estrategias y sus guardas, también. F3 fue conectar ambos extremos.

### Decisiones aplicadas

- **Regla efectiva heredada.** Si la rutina no fija regla para un ejercicio, se usa la
  que el catálogo declara para él, y la UI lo dice ("heredada del catálogo"). No es
  suponer: está escrita, solo que en otro sitio. La alternativa —exigirla explícita—
  dejaba sin progresión todas las rutinas creadas en F1.
- **Alcance por ejercicio, no por rutina.** El historial que alimenta el motor y el
  cooldown cuentan el ejercicio en todas las rutinas, incluidos los entrenamientos
  ad-hoc: el músculo no distingue de qué rutina venía el estímulo.
- **Un lote, una versión.** Progresar tres ejercicios crea *una* versión con los tres
  cambios y *tres* eventos, no tres versiones.
- **Aplicar re-evalúa.** El cliente elige *qué* ejercicios progresan; *cuánto* lo decide
  el motor en el servidor cada vez. Ningún cliente puede pedir un salto que las guardas
  no permitirían.
- **Deshacer estricto.** Si el plan cambió después de la progresión, deshacer se niega
  con el motivo en vez de pisar esa edición. Una reversión libera el cooldown: esperar
  una semana por una subida que ya no está sería castigar por nada.

**Aprendido en F3** — tres cosas, y ninguna estaba en el plan:

1. **El editor perdía la regla de progresión.** Desde F1, guardar una rutina no enviaba
   `rule_slug`, así que cada guardado lo borraba en silencio. Nadie lo notó porque hasta
   F3 ese campo no se leía. Es el mismo patrón que el calentamiento descartado: *si el
   backend soporta algo, la UI debe poder producirlo y no destruirlo*.
2. **Un test verde que no probaba nada.** El primer test del cooldown pasaba por
   casualidad: `applied_at` es un instante de auditoría que pone el reloj real, no la
   fecha inyectada, y resultaba posterior a la fecha del test. Se arregló fijando el
   instante explícitamente. La fecha se inyecta en el dominio, pero la auditoría no
   —ni debe—, y esa frontera hay que tenerla presente al escribir el test.
3. **La casilla de selección salía encima del nombre.** El `label` global apila etiqueta
   e input en columna, que es lo correcto en un formulario y lo contrario de lo que pide
   una casilla. Solo se vio abriendo la app; ningún test lo habría cogido.

---

## F4 · Métricas y ranking muscular

**Objetivo:** la característica visual insignia.
**Completada:** 2026-09-07
**Criterio de aceptación:** ver de un vistazo qué músculos van por delante y por detrás, y
poder responder «¿por qué este rango?» sin salir de la pantalla. ✅ Verificado en la app real.

- [x] Servicio de métricas: volumen, frecuencia, e1RM, evolución por ejercicio y músculo
- [x] Aplanado historial → `StimulusEvent` por músculo
- [x] SVG del cuerpo (frontal y dorsal) con `svg_key` por grupo muscular
- [x] Colores por tier + halo de actividad
- [x] Ficha de músculo: score, factores, ejercicios, histórico, qué falta para el siguiente tier
- [x] `muscle_score_snapshot` semanal, reconstruible
- [x] Calibración provisional de `reference_ratio` por músculo, editable desde ajustes
      *(D9 sigue abierta: la validación con datos reales necesita meses de historial)*
- [x] Avisos de equilibrio empuje/tirón y cuádriceps/femoral *(M7)*

Sin migraciones: `muscle_score_snapshot` y la fórmula `ranking/v1` estaban desde F0.

### Decisiones aplicadas

- **La referencia es el techo de la escalera, no una marca de élite.** `reference_ratio`
  se fijó al **doble** de una marca élite amateur. Con la referencia puesta en la marca
  élite, un principiante aparecía en Platinum el primer mes y la escalera se agotaba
  antes de empezar. Con la calibración actual: principiante en Iron–Bronze, dos o tres
  años constantes en Gold–Platinum, nivel avanzado en Diamond–Ascendant.
- **Umbrales editables sin tocar código** (ADR-0003): el ajuste `ranking_reference_ratio`
  sobrescribe la tabla del dominio; los valores no positivos se ignoran en vez de romper
  la escala.
- **Snapshot semanal al arrancar**, igual que la copia de seguridad, y **nunca vacío**:
  un punto donde ningún músculo tiene rango no es información.
- **La misma información por dos caminos**: mapa y lista. El mapa solo funciona si
  distingues los colores; la lista funciona siempre.

**Aprendido en F4** — tres cosas:

1. **La calibración inicial premiaba lo que no se había entrenado.** Antebrazo y bíceps
   salían Radiant sin haber hecho un solo curl: cobraban media marca del peso muerto y
   de las dominadas como secundarios, y su referencia estaba pensada para el peso que
   mueven *directamente*. Un ranking se valida mirando a quién corona, no solo
   comprobando que la fórmula suma bien.
2. **El arranque del servidor guardaba un histórico de ceros.** `snapshot_if_stale` se
   ejecuta al arrancar; con la base recién creada dejaba 18 filas en «sin datos» que
   luego aparecían como un valle en la gráfica. Lo detectó un test de la API que
   esperaba un punto y encontró dos.
3. **Un import circular avisando de un error de capas.** `views` necesitaba un modelo
   que estaba en `services/metrics`, y `metrics` importaba repositorios que importan
   `views`. La solución no fue romper el ciclo a la fuerza sino colocar bien la pieza:
   los modelos de lectura viven todos en `views`.

---

## F5 · Temporizador

**Objetivo:** que sea cómodo entrenar con la app abierta.

- [ ] Temporizador persistente entre pestañas
- [ ] Iniciar, pausar, reiniciar, finalizar
- [ ] Presets rápidos (60/90/120/180 s)
- [ ] Descanso por defecto tomado del ejercicio
- [ ] Sonido y notificación

**Fuera de alcance a propósito:** temporizadores encadenados por rutina, distinción entre
descanso entre series y entre ejercicios, cronómetro de sesión total. Complican el modelo
sin valor demostrado.

---

## F6 · Agente de IA

**Objetivo:** un contrato estable y auditable para el agente externo, sin acoplar Fit-Up a
ninguna IA concreta.

- [ ] Servidor MCP sobre los mismos casos de uso (wrappers finos)
- [ ] Tools de lectura: rutinas, historial, calendario, estadísticas, ranking, tendencias
- [ ] Tools de propuesta (no escriben)
- [ ] Scopes en configuración local, escrituras sensibles desactivadas por defecto
- [ ] `AuditLog` de toda operación del agente
- [ ] Claves de idempotencia en escrituras
- [ ] Backup automático antes de un lote de escrituras del agente
- [ ] Documentar el contrato "usa la API, no el fichero"
- [ ] Documentar la frontera datos/instrucciones en las descripciones de las tools

### Decisión diferida a esta fase
**D5 — ¿Bandeja de propuestas (`AgentProposal`)?** Con un agente autónomo puede ser
ceremonia innecesaria, o el punto de control que se quiera conservar para los cambios de
rutina. Se decide con historial real y el agente funcionando.

---

## F7 · Pulido

- [ ] PWA offline en modo lectura *(mitiga el "PC apagado" de ADR-0001)*
- [ ] Accesibilidad: contraste, targets ≥ 44 px, uso con una mano
- [ ] Rendimiento con años de historial
- [ ] Import desde export JSON (restauración)
- [ ] Revisión de la calibración del ranking con datos reales

### Decisión diferida
**D6 — ¿Registro offline desde el móvil con cola y sincronización?** Solo si el uso real
lo justifica.

---

## Mejoras propuestas y su destino

| # | Mejora | Fase |
|---|---|---|
| M1 | RIR/RPE opcional por serie | F1 |
| M2 | Peso corporal + `load_factor` | F0 ✅ / F1 (UI) |
| M3 | Deload sugerido | F3 ✅ |
| M4 | Bandeja de propuestas | F6 (diferida) |
| M5 | Export/import JSON + backup automático | F1 |
| M6 | Estado "Sin datos" ≠ Iron | F0 ✅ |
| M7 | Avisos de equilibrio muscular | F4 ✅ |
| M8 | Cadena de variantes para calistenia | F0 ✅ (motor) / F3 ✅ (UI) |
| M9 | Estado `partial` de sesión | F0 ✅ (esquema) / F1 (UI) |
| M10 | Ciclos rotativos A/B/C | Sin programar; el esquema lo contempla |

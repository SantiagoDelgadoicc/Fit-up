# Plan de implementación

Documento vivo. Se marca cada casilla al completar el hito y se actualiza la tabla de
estado. Cada fase termina en un incremento **usable**, no en una capa técnica a medias.

**Estado global: en pruebas y pulido.** F0–F6 completadas, más dos ajustes del modelo
salidos del uso real (varias sesiones por día y series al fallo, ver
[abajo](#ajustes-del-modelo-salidos-del-uso-real)).

La app se usa a diario y la funcionalidad está completa, pero lleva poco tiempo en uso
real: lo que queda es encontrar asperezas usándola. Dos cosas siguen explícitamente sin
validar y así se presentan en la interfaz:

- **La calibración del ranking** (D9). Los umbrales están razonados, no confirmados con
  datos reales; confirmarlos necesita meses de historial.
- **Los permisos del agente**, que aún no ha ejercitado ningún agente de verdad.

Ninguna de las dos compromete el historial, que es inmutable, versionado, auditado y con
copia diaria.

| Fase | Objetivo | Estado |
|---|---|---|
| [F0](#f0--fundamentos) | Base técnica: esquema, dominio, catálogo, CI | ✅ Completada |
| [F1](#f1--mvp-de-registro) | Registrar entrenamientos a diario | ✅ Completada |
| [F2](#f2--calendario-y-cumplimiento) | Ver adherencia en un calendario mensual | ✅ Completada |
| [F3](#f3--progresión) | Aplicar sobrecarga progresiva con un botón | ✅ Completada |
| [F4](#f4--métricas-y-ranking-muscular) | Mapa corporal con rangos Iron→Radiant | ✅ Completada |
| [F5](#f5--temporizador) | Descansos durante el entrenamiento | ✅ Completada |
| [F6](#f6--agente-de-ia) | Contrato estable para el agente local | ✅ Completada |
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

**Resuelto después:** el dibujo geométrico se sustituyó por una silueta anatómica
(M11, ver más abajo). El contrato aguantó: solo cambiaron las formas.

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
**Completada:** 2026-09-07

- [x] Temporizador persistente entre pestañas
- [x] Iniciar, pausar, reiniciar, finalizar
- [x] Presets rápidos, **tres** (2:00 · 1:30 · 4:00) y editables desde la pantalla
- [x] Descanso por defecto tomado del ejercicio: un botón por ejercicio en «Hoy»
- [x] Sonido y notificación

**Fuera de alcance a propósito:** temporizadores encadenados por rutina, distinción entre
descanso entre series y entre ejercicios, cronómetro de sesión total. Complican el modelo
sin valor demostrado.

### Decisiones aplicadas

- **Se guarda el instante de fin, no los segundos restantes.** Un contador que se
  decrementa se desincroniza en cuanto el navegador ralentiza la pestaña en segundo
  plano, que es exactamente lo que pasa con el móvil en el bolsillo. Con un instante
  absoluto el restante se recalcula del reloj y da igual cuántos ticks se pierdan.
- **Tres presets y no cuatro.** El plan preveía 60/90/120/180. En el gimnasio se elige de
  un vistazo y el cuarto botón solo añadía una decisión. Viven en el ajuste
  `timer_presets_s`, que ya existía, y se editan desde la propia pantalla.
- **Sin fichero de audio.** El aviso son tres tonos sintetizados con WebAudio: un `.mp3`
  en el repositorio es un binario que versionar y servir para 200 ms de sonido.
- **Store compartido en el módulo, no solo `localStorage`.** El evento `storage` avisa a
  las *otras* pestañas, nunca a la que escribió. Sin store, la píldora de la navegación
  no se enteraba de que el descanso había empezado en su misma pestaña.

**Aprendido en F5:** los tres fallos aparecieron al usar la app, no en los tests — la
píldora que no reaccionaba, el estilo de pestaña que la apilaba en vertical, y la octava
entrada de la barra inferior que cortaba el texto de «Ajustes» en 375 px.

---

## F6 · Agente de IA

**Objetivo:** un contrato estable y auditable para el agente externo, sin acoplar Fit-Up a
ninguna IA concreta. El agente **es otro proyecto**: aquí solo se construye la puerta.

Contrato completo en [03-contrato-del-agente.md](03-contrato-del-agente.md).

- [x] **Servidor MCP** sobre los mismos casos de uso (wrappers finos): 16 tools por stdio
- [x] Tools de lectura: 10, y la API HTTP + OpenAPI las cubre también
- [x] Tools de propuesta (no escriben): permiso `propose`, en MCP y en HTTP
- [x] Scopes en configuración local, escrituras sensibles desactivadas por defecto
- [x] `AuditLog` de toda operación del agente, **y legible** vía `GET /api/auditoria`
- [x] Claves de idempotencia en escrituras de sesión
- [x] Backup automático antes de un lote de escrituras del agente
- [x] Documentar el contrato "usa la API, no el fichero"
- [x] Documentar la frontera datos/instrucciones

### Lo que había que arreglar antes de nada

La auditoría existía desde F0 pero **no servía para lo que iba a hacer falta**:

1. **La API no permitía declarar el actor.** Cualquier escritura del agente quedaba
   registrada como `usuario`. La traza —que según ADR-0004 es *la* protección— no
   distinguía nada. Resuelto con la cabecera `X-Fitup-Actor`.
2. **`audit_log` se escribía pero no se leía.** Ningún endpoint la exponía: un cajón
   cerrado. Resuelto con `GET /api/auditoria`.
3. **Solo auditaban sesiones y progresiones.** Rutinas, semana, excepciones, ajustes y
   peso escribían sin dejar rastro. Ahora auditan todas.

### Decisiones aplicadas

- **Los permisos son por familia, no por endpoint.** `write_sessions`, `write_routines` y
  `write_settings` agrupan operaciones que se conceden juntas o no se conceden. Una lista
  de treinta permisos no la revisa nadie.
- **`read` se aplica al router entero**, no endpoint a endpoint: es el interruptor general
  del agente y apagarlo tiene que dejarlo fuera de todo, no solo de lo que alguien se
  acordó de marcar.
- **Un rechazo se audita.** `result='rechazado'` estaba en el CHECK del esquema desde F0
  sin usarse. Un intento bloqueado dice más que uno permitido.
- **Un actor desconocido devuelve 400**, no se degrada a `usuario`: una cabecera mal
  escrita dejaría al agente operando de incógnito.
- **La copia previa al lote se corta por inactividad** (30 min). El agente no anuncia
  dónde empieza ni acaba un lote; lo que se puede medir es cuánto lleva sin tocar nada.
  Una copia por escritura llenaría el disco durante una ráfaga.
- **Las copias del agente y las diarias se podan por separado.** Con un `fitup-*.db` a
  secas, la diaria barría las del agente y al revés — la copia previa a un lote habría
  desaparecido justo cuando hiciera falta.

### El servidor MCP

Se construyó al confirmarse que habrá **más de una app de este estilo**. Con una sola, MCP
ahorra escribir un cliente HTTP y es prescindible; con varias, un único agente las conecta
todas sin un cliente por cada una, que es justo para lo que se diseñó el protocolo.

Es la primera dependencia añadida desde F0 (`mcp>=2.0`). Pasa el filtro: implementar el
protocolo a mano sería mucho más código que mantener del que ahorra, y es agnóstico de
modelo, así que no ata Fit-Up a ninguna IA.

Dos cosas que salieron al probarlo contra un cliente MCP real, no en los tests:

- **El SDK solo deja llegar al modelo el texto de un `ToolError`.** Cualquier otra
  excepción le llega como «error inesperado». Un agente al que le dicen «error» no puede
  corregirse; uno al que le nombran el permiso que falta, sí. Los errores de aplicación se
  traducen, igual que el adaptador HTTP los traduce a códigos de estado.
- **La conversión de la entrada tenía que ir dentro del traductor**, no antes: una fecha
  mal escrita se escapaba como `ValueError` pelado.

La política de permisos se movió de `api/` a `application/services/agent.py`. Tenerla en un
adaptador obligaba al otro a importarlo, y eso convierte a dos hermanos en padre e hijo
(invariante 6).

### Decisión diferida a esta fase
**D5 — ¿Bandeja de propuestas (`AgentProposal`)?** Con un agente autónomo puede ser
ceremonia innecesaria, o el punto de control que se quiera conservar para los cambios de
rutina. Sigue abierta a propósito: se decide con historial real y el agente funcionando.

---

## F7 · Pulido

- [x] **Sustituir el mapa corporal por una silueta anatómica** *(M11)*. Hecho con los
      trazados de [MuscleMap](https://github.com/melihcolpan/MuscleMap) (tag 1.6.4, MIT),
      extraídos de sus fuentes Swift a `frontend/src/components/bodyPaths.ts`. El
      contrato se mantuvo entero: una zona por `svg_key`, dos vistas, y los cuatro
      estados pintados desde CSS. El catálogo, el esquema y el ranking no se tocaron.
- [ ] PWA offline en modo lectura *(mitiga el "PC apagado" de ADR-0001)*
- [ ] Accesibilidad: contraste, targets ≥ 44 px, uso con una mano
- [ ] Rendimiento con años de historial
- [ ] Import desde export JSON (restauración)
- [ ] Revisión de la calibración del ranking con datos reales

### Decisión diferida
**D6 — ¿Registro offline desde el móvil con cola y sincronización?** Solo si el uso real
lo justifica.

---

## Ajustes del modelo salidos del uso real

Dos supuestos del diseño original no aguantaron el primer contacto con una rutina de
verdad. Ninguno estaba en el plan; ambos salieron de intentar cargar la rutina real.

### Un día, varios entrenamientos

**El supuesto:** un día tiene como mucho un entrenamiento. Estaba en la capa de
aplicación (`Conflict` explícito, `session_on()` devolviendo una sola) y en el plan
semanal (`dict weekday → una rutina`).

**Por qué falla:** partir el volumen entre mañana y tarde es corriente en calistenia.
Juntarlo todo en una sesión perdía el dato de cuál se saltó, y obligaba a esperar a la
noche para anotar lo de la mañana.

**Lo que se cambió.** El esquema no hizo falta tocarlo: `workout_session` nunca tuvo
`UNIQUE` en `date`, y `schedule_slot` tiene `id` propio sin `UNIQUE` por día. El diseño
original ya lo contemplaba; la restricción era de la capa de arriba.

- `resolve_day_state` recibe `scheduled_count` y una lista de sesiones.
- `DayView` pasa a `scheduled` (una entrada por rutina, con su sesión si la hay) y
  `extra_sessions`.
- El plan semanal admite varias rutinas por día, en orden.
- «Hoy» y el calendario pintan una tarjeta por rutina.

**La decisión de diseño que hubo que tomar:** si tocaban dos rutinas y solo se hizo una,
el día queda **pendiente mientras haya margen** y parcial después. Es el mismo principio
que sostiene todo el módulo —no registrado no es no realizado— aplicado dentro del día:
por la tarde todavía puede entrenarse, así que llamarlo parcial adelanta el veredicto.

### Series al fallo

**El supuesto:** toda serie tiene un objetivo numérico. El esquema lo imponía con
`CHECK (target_reps IS NOT NULL OR target_time_s IS NOT NULL)`.

**Por qué falla:** «pantorrillas 3 × fallo» no tiene objetivo. Rellenarlo con una
estimación sería inventar el plan, justo lo que prohíbe el invariante 5.

**Lo que se cambió:** migración `0002`, columna `to_failure` en `planned_set`. Hubo que
recrear la tabla porque SQLite no permite modificar un `CHECK` en sitio. Ahora hay tres
formas válidas de prescribir una serie —repeticiones, tiempo o al fallo— y una cuarta
prohibida: al fallo **con** repeticiones objetivo, que es una contradicción.

El catálogo suma nueve ejercicios que la rutina real necesitaba y no existían: flexiones
abiertas, toque de talón, estrellitas, Arnold press, curl con arm blaster, dominadas
abiertas y mixtas, sentadilla goblet y saltos de cuerda.

### Pendiente conocido

Registrar «de un toque» una rutina con series al fallo anota la serie **sin
repeticiones**: el sistema no puede saber cuántas se hicieron. Aparece como `?` en el
historial hasta que se edite. Es honesto —no se inventa el dato— pero incómodo, y la
edición de series registradas todavía no existe.

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
| M11 | Silueta anatómica para el mapa corporal | F7 ✅ |

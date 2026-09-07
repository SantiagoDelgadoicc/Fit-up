# Fit-Up — Análisis y Arquitectura (Fase 0)

Fecha: 2026-09-06 · Estado: **propuesta, pendiente de aprobación**

---

## 1. Comprensión del proyecto

Fit-Up es una app **personal, monousuario, local-first** para planificar, registrar y progresar entrenamiento.

Tensiones centrales que definen el diseño:

| Tensión | Implicación |
|---|---|
| Plan vs realidad | Dos modelos separados; la rutina editable no puede corromper el historial ya registrado |
| Registro diferido (1–2 veces/semana) | El registro retroactivo es el caso **principal**, no una excepción |
| "No registrado" ≠ "no realizado" | Hace falta un estado **PENDIENTE** con ventana de gracia |
| Progresión automática vs seguridad | El motor **propone**, el humano **aplica**; y sabe decir "no sé" |
| Ranking motivador vs métrica honesta | Separar *cantidad de entrenamiento* de *desarrollo/capacidad* |
| Uso en el gimnasio vs agente en el PC | El punto de consumo de la UI y el del agente pueden no ser la misma máquina |

**Alcance explícitamente excluido:** multiusuario, nube, sincronización como servicio, redes sociales, nutrición.

### Ambigüedades detectadas (requieren decisión o default explícito)

| # | Ambigüedad | Propuesta |
|---|---|---|
| A1 | "Rutina por día": ¿semana fija o ciclo rotativo (A/B/C cada N días)? | Semana fija en v1; esquema preparado para ciclo |
| A2 | Editar una rutina, ¿altera el historial pasado? | No: versionado inmutable de rutinas |
| A3 | ¿Cuándo un día programado pasa a "no cumplido"? | Ventana de gracia configurable (default 3 días) + marcado manual |
| A4 | ¿La progresión modifica el plan o solo sugiere? | Modifica el plan creando **nueva versión**, siempre por acción explícita y reversible |
| A5 | Ejercicios sin carga externa (calistenia, isométricos, tiempo) | `load_factor` por ejercicio → todo se normaliza a kg-equivalentes |
| A6 | Músculos sin ningún ejercicio asociado | Estado **Sin datos**, no "Iron" (honestidad > gamificación) |
| A7 | Unilateralidad (por lado) | Flag en el ejercicio; el volumen cuenta por lado |
| A8 | Zona horaria / límite de día | Se almacena **fecha local ISO**, nunca timestamp UTC, para el concepto "día de entrenamiento" |
| A9 | Deload / descarga planificada | Contraparte necesaria de la sobrecarga; propuesta como mejora |

---

## 2. Reglas de negocio identificadas

### 2.1 Planificación
- **R1.** Una **rutina** existe en **versiones inmutables**. Editarla crea `version_no + 1`.
- **R2.** Una sesión histórica referencia la **versión concreta** vigente al ejecutarse. El historial nunca cambia retroactivamente.
- **R3.** El calendario semanal asigna rutinas a días con vigencia (`active_from` / `active_to`), permitiendo cambiar la planificación sin reescribir el pasado.
- **R4.** Las excepciones puntuales (descanso, lesión, viaje) se modelan como `ScheduleException`, no como incumplimiento.

### 2.2 Registro
- **R5.** Se puede registrar cualquier fecha pasada o presente. Fechas futuras: prohibidas.
- **R6.** Registro por defecto = **"lo hice como estaba planificado"** (un solo toque). Las desviaciones se editan encima.
- **R7.** Una sesión puede ser `completed`, `partial` o `skipped` (registro explícito de no realización).
- **R8.** Puede existir sesión sin rutina programada (`ad-hoc`); cuenta para volumen, no para cumplimiento.
- **R9.** Toda sesión guarda `logged_at` además de `date`, para distinguir registro en vivo de retroactivo y auditar la calidad del dato.

### 2.3 Estado de cumplimiento del día (máquina de estados, derivada)

| Estado | Condición | Calendario |
|---|---|---|
| `REST` | Sin rutina programada y sin sesión | ⚪ |
| `DONE` | Sesión `completed` | 🟢 |
| `PARTIAL` | Sesión `partial` | 🟡 |
| `PENDING` | Programado, sin sesión, dentro de la ventana de gracia | 🟠 (borde punteado) |
| `MISSED` | Programado, sin sesión, fuera de la ventana **o** marcado `skipped` | 🔴 |
| `EXTRA` | Sesión sin rutina programada | 🔵 |
| `EXCUSED` | Excepción registrada (descanso/lesión/viaje) | ⚫ |

> Esto resuelve explícitamente "no registrado ≠ no realizado": `PENDING` es un tercer estado real, no un 🔴 prematuro. Solo `MISSED` afecta a la adherencia; `PENDING` se **excluye** del cálculo en lugar de contarse como fallo.

### 2.4 Progresión
- **R10.** La progresión es una **función pura** `(historial, plan_actual, regla, hoy) → resultado`. Sin I/O.
- **R11.** Resultado como tipo discriminado: `READY` | `NOT_YET` | `UNDETERMINED` | `DELOAD_SUGGESTED`. **Nunca se inventa una progresión.**
- **R12.** Nunca se progresa con menos de 2 sesiones registradas del ejercicio.
- **R13.** Guardas obligatorias: incremento máximo semanal, cooldown mínimo entre progresiones, techos absolutos (`rep_max`, `set_max`, `time_max`), bloqueo si la última sesión fue peor que la anterior.
- **R14.** Aplicar una progresión genera una nueva versión de rutina + un `ProgressionEvent` auditable y **reversible**.

### 2.5 Métricas
- **R15.** Nada derivable se persiste como dato permanente. Excepción justificada: `MuscleScoreSnapshot` (para graficar la evolución histórica del rango), marcado como caché reconstruible con `formula_version`.
- **R16.** Toda métrica mostrada debe ser **explicable**: la UI puede mostrar de qué números sale.

---

## 3. Modelo del dominio

### 3.1 Entidades por naturaleza del dato

**Permanentes (catálogo)**
- `MuscleGroup(id, nombre, region, lado, svg_key, orden)`
- `Exercise(id, nombre, modalidad[reps|tiempo|distancia], tipo_carga[externa|corporal|asistida|ninguna], load_factor, es_unilateral, equipamiento, regla_progresion_default, variante_siguiente_id?, activo)`
- `ExerciseMuscle(exercise_id, muscle_id, rol[primario|secundario|estabilizador], factor)`
- `ProgressionRule(id, nombre, estrategia, params_json, guardas_json)`
- `Settings(unidades, inicio_semana, dias_gracia, timer_defaults, ranking_formula_version, peso_corporal)`

**Planificados**
- `Routine(id, nombre, estado)` → `RoutineVersion(id, routine_id, version_no, creada_en, nota)`
- `RoutineExercise(id, routine_version_id, exercise_id, orden, descanso_seg, regla_override, notas)`
- `PlannedSet(id, routine_exercise_id, n_serie, reps_objetivo, reps_max?, peso_objetivo?, tiempo_objetivo?, rir_objetivo?, es_calentamiento)`
- `ScheduleSlot(id, dia_semana, routine_id, active_from, active_to)`
- `ScheduleException(fecha, routine_id?, motivo)`

**Históricos**
- `WorkoutSession(id, fecha, routine_version_id?, origen[planificada|adhoc], estado[completed|partial|skipped], esfuerzo?, duracion?, notas, logged_at)`
- `SessionExercise(id, session_id, exercise_id, orden, planned_ref?)`
- `SessionSet(id, session_exercise_id, n_serie, reps?, peso?, tiempo_s?, rir?, completada, es_calentamiento)`
- `ProgressionEvent(id, exercise_id, version_origen, version_destino, regla, antes_json, despues_json, aplicada_en, actor[usuario|agente], revertida)`
- `BodyweightLog(fecha, peso)`
- `AuditLog(ts, actor, accion, payload, resultado)`

**Derivados (calculados; snapshot solo donde se justifica)**
- Volumen efectivo, e1RM, frecuencia, adherencia, tendencias, `MuscleScore`
- `MuscleScoreSnapshot(fecha, muscle_id, score_desarrollo, score_carga, rango, formula_version, inputs_json)` — caché reconstruible
- `AgentProposal(id, tipo, diff_json, estado[pendiente|aprobada|rechazada], creada_por, motivo)`

### 3.2 Decisión de modelado clave: series explícitas
`PlannedSet` como **filas explícitas** (3×15 → 3 filas) en lugar de `sets=3, reps=15`.
Coste: más filas. Beneficio: pirámides, drop sets, series de aproximación, progresión por serie individual, y **una sola forma** de comparar planificado vs realizado (fila a fila). La UI genera las filas automáticamente; el usuario nunca las escribe a mano.

### 3.3 Normalización de carga (`load_factor`)
Para que un fondo, una plancha y un press banca sean comparables en el ranking, cada serie se convierte a **kg-equivalentes**:

```
carga_efectiva = peso_externo + (peso_corporal × load_factor)
volumen_serie  = carga_efectiva × reps × (2 si unilateral)          [modalidad reps]
volumen_serie  = carga_efectiva × (segundos / 3) × factor_iso       [modalidad tiempo]
```

`load_factor` es dato del catálogo (flexión ≈ 0.64, dominada ≈ 1.0, fondo ≈ 1.0, sentadilla libre ≈ 0.85 del peso corporal). Es una aproximación **documentada y editable**, no una verdad física.

---

## 4. Arquitectura propuesta

### 4.1 Forma general — núcleo puro + adaptadores

> **Nota de estado.** El árbol que sigue es el diseño propuesto. El real, más plano,
> está en [CLAUDE.md](../CLAUDE.md): `backend/src/fitup/{domain,application,infrastructure,api}`.
> `apps/agent/` no existe todavía — el servidor MCP sigue pendiente.

```
apps/
  web/                 UI (SPA/PWA)
  api/                 adaptador HTTP (delgado) + OpenAPI
  agent/               servidor MCP (delgado) para la IA local
core/
  domain/              entidades, VOs y reglas PURAS (sin I/O, sin reloj)
    progression/       estrategias + guardas
    ranking/           scoring v1 + tiers
    compliance/        máquina de estados del día
    metrics/           volumen, e1RM, frecuencia, adherencia
  application/         casos de uso (LogWorkout, ApplyProgression, GetCalendar…)
                       + política de permisos
  infrastructure/      repositorios SQLite, migraciones, backups
```

**Invariante arquitectónico:** `apps/api` y `apps/agent` son **dos adaptadores sobre los mismos casos de uso**. El agente de IA no tiene un camino privilegiado ni puede saltarse una regla de negocio: es física de la arquitectura, no disciplina del programador.

**Dominio puro:** sin acceso a BD, sin `now()` implícito (la fecha se inyecta). Consecuencia directa: los tests de progresión y ranking son deterministas y triviales — exactamente donde vive el riesgo del proyecto.

### 4.2 Persistencia
- **SQLite** en archivo único (`data/fitup.db`), WAL activado. Volumen esperado: decenas de miles de filas en años. Sobra.
- Migraciones versionadas desde el día 1 (los datos del usuario son irreemplazables).
- Backup automático diario por copia del archivo + export JSON completo, documentado y legible por humanos y por la IA.
- El repositorio expone objetos de dominio, no filas.

### 4.3 Distribución
Decisión abierta — ver `docs/01-decisiones-pendientes.md` (D1). Determina si la app es accesible desde el móvil durante el entrenamiento.

---

## 5. Sistema de progresión

### 5.1 Estrategias configurables por ejercicio

| Estrategia | Params | Comportamiento |
|---|---|---|
| `reps_lineal` | `rep_min, rep_max, incremento` | +1 rep hasta `rep_max` |
| `doble_progresion` | `rep_min, rep_max, incr_peso` | sube reps hasta el techo; al llegar, +peso y reset a `rep_min` |
| `peso_lineal` | `incremento` o `incremento_pct` | +X kg cuando se cumplen todas las series |
| `series` | `set_max` | +1 serie hasta el techo |
| `tiempo` | `t_min, t_max, incremento_s` | +N segundos |
| `variante` | cadena ordenada de ejercicios | flexión rodillas → normal → declinada → arquera |
| `manual` | — | nunca sugiere |

> `doble_progresion` es la estrategia por defecto recomendada: evita el fallo clásico de subir repeticiones indefinidamente sin tocar nunca la carga.

### 5.2 Condición de disparo (gate)
Se ofrece progresión solo si, en las **últimas 2 sesiones** de ese ejercicio: todas las series objetivo completadas **y** reps ≥ objetivo **y** (si hay RIR registrado) RIR ≥ 1.

### 5.3 Guardas
- Incremento máximo semanal (default: ≤10 % de carga o +1 unidad, lo que sea menor).
- Cooldown mínimo entre progresiones del mismo ejercicio (default: 7 días).
- Techos absolutos por regla.
- Bloqueo por regresión: si la última sesión rindió por debajo de la anterior → no progresa; con 2 regresiones seguidas → `DELOAD_SUGGESTED`.
- Mínimo 2 sesiones registradas.

### 5.4 Salida del motor

```
READY             → propuesta concreta + justificación legible + diff del plan
NOT_YET           → motivo ("falta 1 sesión cumpliendo objetivo", "cooldown: 3 días")
UNDETERMINED      → motivo ("ejercicio sin regla", "peso no registrado en las últimas sesiones")
DELOAD_SUGGESTED  → propuesta de descarga + motivo
```

`UNDETERMINED` es un estado de primera clase y se muestra en la UI. Requisito explícito: **no inventar**.

### 5.5 Aplicación
Botón "Progresar" → preview del diff → confirmar → nueva `RoutineVersion` + `ProgressionEvent`.
Deshacer = nueva versión que revierte. Nunca se borra historia.

---

## 6. Ranking muscular

### 6.1 Separación conceptual obligatoria

| Métrica | Qué representa | Ventana | Dinámica |
|---|---|---|---|
| **Carga / Actividad** | Cuánto estás entrenando ese músculo *ahora* | 28 días, ponderación exponencial | Volátil: sube y baja rápido |
| **Desarrollo / Capacidad** | De qué eres capaz con ese músculo | mejores marcas 90–180 días | Lenta, con trinquete, decae poco |

**Propuesta:** el **rango Iron→Radiant representa Desarrollo** (lento, se gana y casi no se pierde: honesto y motivador). La **Actividad** se muestra como indicador secundario sobre el mismo músculo (halo: verde = estimulado esta semana, gris = sin estímulo reciente).
Un solo mapa corporal comunica dos cosas distintas sin mezclarlas.

### 6.2 Esbozo de fórmula v1 (versionada y editable)

```
Para cada músculo m:
  contribución(ejercicio→m) = factor_rol   (primario 1.0 / secundario 0.5 / estabilizador 0.2)

  CARGA(m)      = EWMA_28d( Σ volumen_efectivo(serie) × contribución )
                  × f_frecuencia(sesiones/semana con estímulo en m)
                  × f_consistencia(semanas consecutivas con estímulo)

  DESARROLLO(m) = Σ_ejercicios( top3(e1RM_equivalente) × contribución ) normalizado
                  × (1 + bonus_progresión)       # premia progresar, no solo acumular
                  × decay(semanas_sin_estímulo)  # suave, con suelo

  RANGO(m)      = tier( DESARROLLO(m) )  →  Iron … Radiant
```

- `e1RM_equivalente` con Epley sobre carga efectiva; para modalidad tiempo, equivalencia documentada.
- `bonus_progresión` es lo que hace que el rango **suba al aplicar sobrecarga progresiva**, cumpliendo el requisito explícito.
- `decay` con **suelo**: nunca se pierde más de 1 tier respecto al pico en 8 semanas. Descansar no debe castigar.
- Músculo sin ejercicios asociados → **Sin datos** (gris), no Iron.

### 6.3 Mapeo score → tier
Resuelto en [ADR-0003](adr/0003-ranking-desarrollo-con-halo-actividad.md) e implementado en F4: **umbrales absolutos anclados al peso corporal**, con la tabla `reference_ratio` por músculo en `domain/ranking/calibration.py` y editable desde ajustes.
La calibración es **provisional** (D9): el tope de la escala se fijó al doble de una marca de élite amateur para que la escalera tenga recorrido durante años, y se validará con historial real.

### 6.4 Explicabilidad (no negociable)
Tocar un músculo abre: rango, score, los 3 factores que más aportan, ejercicios contribuyentes, sparkline del rango y **qué haría falta para el siguiente tier**.
Sin esto el ranking es un número mágico, pierde credibilidad — y el agente de IA no puede razonar sobre él.

### 6.5 Versionado de fórmula
`ranking/v1` puro + `formula_version` en config y en cada snapshot. v2 puede coexistir y recalcular todo el histórico desde el registro crudo.

---

## 7. IA e integración

> **Nota de estado (F6).** Esta sección es el análisis inicial. Tres puntos los
> reemplazó después [ADR-0004](adr/0004-integracion-con-agente-externo-autonomo.md), y lo
> construido sigue al ADR, no a lo de aquí. El contrato vigente está en
> [03-contrato-del-agente.md](03-contrato-del-agente.md):
>
> 1. **La superficie principal es HTTP + OpenAPI**, no MCP. MCP sigue previsto como
>    segunda superficie, pero está pendiente y no es imprescindible.
> 2. **La bandeja de propuestas no es obligatoria.** Frente a un agente autónomo puede ser
>    ceremonia inútil; quedó diferida como D5, todavía abierta.
> 3. **Los scopes no contienen al agente.** Protegen contra sus equivocaciones, no contra
>    un agente hostil: un proceso con control del PC se los salta. Lo que protege el
>    historial es inmutabilidad, auditoría, deshacer y copias.

### 7.1 Superficie de integración
**MCP (Model Context Protocol) por stdio** como superficie principal, envolviendo los casos de uso; **OpenAPI/REST** como secundaria (ya existe por la UI y sirve a cualquier cliente no-MCP).
MCP es el estándar de facto para agentes locales, es agnóstico de modelo (Claude, Ollama, cualquiera) y no acopla Fit-Up a ninguna IA concreta. No se duplica lógica: son wrappers finos.

### 7.2 Herramientas expuestas, por ámbito de permiso

| Ámbito | Herramientas |
|---|---|
| `read` | `list_routines`, `get_routine`, `get_history`, `get_calendar`, `get_stats`, `get_muscle_ranking`, `get_exercise_progress`, `detect_trends` |
| `propose` | `propose_progression`, `propose_routine_change` → **solo generan propuestas, no escriben** |
| `write:sessions` | `log_workout`, `add_note` |
| `write:routines` | `apply_progression`, `update_routine` (desactivado por defecto) |

### 7.3 Modelo de permisos y seguridad
- Scopes declarados en fichero de configuración local. Default: `read` + `propose`. Escrituras sensibles **off**.
- Toda operación sensible del agente crea un `AgentProposal` con diff, que el usuario aprueba o rechaza en una **bandeja de sugerencias** en la UI. El agente propone; el humano dispone.
- `AuditLog` de todo lo que hace el agente (actor, acción, payload, resultado).
- Claves de idempotencia en escrituras: un agente reintentando no duplica sesiones.
- Bind a `127.0.0.1` por defecto. Si se expone en LAN, token obligatorio.
- **Regla de frontera:** el contenido devuelto por la BD es dato, no instrucciones. Las notas de texto libre nunca se tratan como órdenes.

### 7.4 Consumo de datos en bruto
Export JSON completo, estable y documentado. Permite a la IA (o a cualquier script) analizar sin depender del proceso vivo de Fit-Up.

---

## 8. UX

### 8.1 Navegación — 5 destinos
`Hoy · Rutinas · Calendario · Cuerpo · Timer` (barra inferior en móvil, lateral en escritorio).

### 8.2 "Hoy" es la pantalla protagonista
- Tarjeta de la rutina del día + botón grande **"✓ Hice esta rutina"** → registra todo como estaba planificado en **un toque**.
- "Ajustar" para desviaciones: solo se editan las excepciones.
- Sección "Pendientes de registrar" con los días en estado `PENDING`, resolubles en un toque.
- Sección "Progresiones disponibles" con los ejercicios en `READY`.

> Principio rector: **registrar-como-planificado por defecto, editar solo lo que difirió.** Es lo que hace realista el registro retroactivo 1–2 veces por semana.

### 8.3 Vista de entrenamiento
Modo lectura de alto contraste, tipografía grande, una tarjeta por ejercicio con series/reps/peso/descanso, check por serie, y temporizador accesible sin salir de la pantalla.

### 8.4 Calendario
Mes navegable, estados con **color + icono** (nunca solo color). Tocar un día muestra qué estaba planificado, qué se hizo y las acciones disponibles.

### 8.5 Cuerpo
SVG frontal/dorsal, músculos coloreados por tier, leyenda de rangos, hoja de detalle explicativa al tocar. Es la característica visual insignia.

### 8.6 Timer
Persistente entre pestañas (no se pierde al navegar), presets rápidos (60/90/120/180 s), descanso por defecto tomado del ejercicio, sonido + notificación.
**Fuera de v1:** temporizadores encadenados por rutina, cronómetro de sesión total.

### 8.7 Accesibilidad y realidad del gimnasio
Tema oscuro por defecto, targets ≥ 44 px, alto contraste, uso con una mano, y nada crítico dependiente solo del color.

---

## 9. Riesgos

| # | Riesgo | Impacto | Mitigación |
|---|---|---|---|
| R1 | Fórmula de ranking arbitraria → desmotiva o miente | Alto | Versionada, explicable, editable, snapshots recalculables |
| R2 | Registro retroactivo → sesgo de memoria, datos pobres | Alto | Prefill desde el plan, estado `PENDING`, registro en un toque |
| R3 | Editar rutinas corrompe el histórico | Alto | Versiones inmutables |
| R4 | Sobrecarga de alcance para un dev solo | Alto | Roadmap por fases; cada fase entrega algo usable |
| R5 | Normalización de calistenia/isométricos es aproximada | Medio | `load_factor` explícito y editable; no presentarlo como exacto |
| R6 | El agente de IA escribe datos malos | Medio | Propuestas + scopes + auditoría + idempotencia |
| R7 | Pérdida de datos (años de historial local) | Alto | Migraciones, backup diario, export JSON, `*.db` fuera de git |
| R8 | PC apagado → app inaccesible desde el móvil | Medio | Depende de D1; mitigación con PWA y caché offline |
| R9 | Progresión demasiado agresiva → lesión | Alto | Guardas duras, cooldown, detección de regresión, deload |
| R10 | Fronteras de fecha / zona horaria | Bajo | Fecha local ISO como clave del día, nunca UTC |
| R11 | Inyección de prompt vía notas de texto libre hacia la IA | Bajo | Contenido de BD tratado como dato, nunca como instrucción |

---

## 10. Estrategia de pruebas

Prioridad por riesgo, no por cobertura uniforme.

| Capa | Qué se prueba | Cómo |
|---|---|---|
| `domain/progression` | Matriz de casos por estrategia, incl. `UNDETERMINED` y `DELOAD` | Tests tabulados + **property-based** para las guardas ("ninguna propuesta supera nunca el techo ni el +10 %") |
| `domain/ranking` | Golden tests con historiales sintéticos; monotonía (más progreso ⇒ score ≥) | Fixtures versionados por `formula_version` |
| `domain/compliance` | Los 7 estados del día, bordes de la ventana de gracia | Tests tabulados |
| `application` | Casos de uso completos | SQLite en memoria |
| `api` | Conformidad con el contrato OpenAPI | Tests de contrato |
| `agent` | Que las tools llaman a los mismos casos de uso y respetan scopes | Tests de permisos: un scope apagado debe fallar |
| `web` | 3 flujos críticos: registrar entrenamiento, aplicar progresión, navegar calendario | Componentes + un smoke E2E |

Objetivo: ~90 % en `domain` (ahí vive el riesgo), pragmático fuera.
**Dataset semilla** de 6 meses sintéticos para probar ranking, gráficos y rendimiento.

---

## 11. Roadmap

Cada fase termina en un incremento usable.

| Fase | Contenido | Resultado |
|---|---|---|
| **F0 Fundamentos** | Decisiones cerradas → ADRs, esquema + migraciones, catálogo semilla de ejercicios y músculos, esqueleto del dominio, CI (lint + tests) | Base sólida |
| **F1 MVP registro** | CRUD rutinas + semana, pantalla "Hoy", registro en un toque, registro retroactivo, historial | **Ya sirve para usarla a diario** |
| **F2 Calendario** | Vista mensual, estados de cumplimiento, excepciones, detalle del día | Visibilidad de adherencia |
| **F3 Progresión** | Reglas, motor, guardas, botón progresar, eventos, deshacer | Objetivo nº 2 cumplido |
| **F4 Métricas + Ranking** | Servicio de métricas, mapa corporal SVG, tiers, explicabilidad, snapshots | Característica insignia |
| **F5 Timer** | Descansos, presets, defaults por ejercicio, sonido/notificación | Uso cómodo en gimnasio |
| **F6 Agente IA** | Servidor MCP, scopes, bandeja de propuestas, auditoría, export JSON | Objetivo nº 8 cumplido |
| **F7 Pulido** | Backups, PWA offline, accesibilidad, rendimiento | Producto terminado |

El timer va en F5: bajo riesgo y alto valor, pero solo cuando ya registras.
El agente va en F6, cuando el modelo de datos ya es estable — construirlo antes garantizaría rehacerlo.

---

## 12. Mejoras propuestas (no incorporadas automáticamente)

| # | Mejora | Por qué | Impacto | ¿Recomendada? |
|---|---|---|---|---|
| M1 | **RIR/RPE opcional por serie** | Es la señal que distingue "progresé porque puedo" de "progresé porque tocaba"; hace la progresión mucho más segura | Bajo coste, alto valor | **Sí, en F1** (campo opcional) |
| M2 | **Peso corporal + `load_factor`** | Sin esto la calistenia no es medible y el ranking se distorsiona | Medio | **Sí, imprescindible para F4** |
| M3 | **Deload sugerido** | Contraparte de la sobrecarga; previene lesión y estancamiento | Medio | **Sí, en F3** |
| M4 | **Bandeja de propuestas** | Sirve al agente *y* a las sugerencias de la propia app: un solo mecanismo de aprobación | Medio | **Sí, en F6** |
| M5 | **Export/import JSON + backup automático** | Años de historial irreemplazable en un archivo local | Bajo | **Sí, temprano (F1)** |
| M6 | **Estado "Sin datos" en el ranking** | Distinguir "músculo débil" de "músculo no medido" | Bajo | **Sí** |
| M7 | **Avisos de equilibrio** (empuje/tirón, cuádriceps/femoral) | El mapa corporal ya tiene los datos; convierte el ranking en algo accionable | Bajo | Sí, F4 |
| M8 | **Cadena de variantes** para calistenia | Única forma correcta de progresar flexiones/dominadas | Medio | Sí, F3 |
| M9 | **Estado `partial` de sesión** | La realidad: a veces se hacen 3 de 5 ejercicios | Bajo | **Sí, en F1** |
| M10 | Ciclos rotativos A/B/C además de semana fija | Muchos programas no son semanales | Medio | Solo si lo necesitas; esquema preparado |

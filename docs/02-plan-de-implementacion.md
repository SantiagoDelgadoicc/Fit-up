# Plan de implementación

Documento vivo. Se marca cada casilla al completar el hito y se actualiza la tabla de
estado. Cada fase termina en un incremento **usable**, no en una capa técnica a medias.

**Estado global:** F0 completada · siguiente F1

| Fase | Objetivo | Estado |
|---|---|---|
| [F0](#f0--fundamentos) | Base técnica: esquema, dominio, catálogo, CI | ✅ Completada |
| [F1](#f1--mvp-de-registro) | Registrar entrenamientos a diario | ⬜ Siguiente |
| [F2](#f2--calendario-y-cumplimiento) | Ver adherencia en un calendario mensual | ⬜ |
| [F3](#f3--progresión) | Aplicar sobrecarga progresiva con un botón | ⬜ |
| [F4](#f4--métricas-y-ranking-muscular) | Mapa corporal con rangos Iron→Radiant | ⬜ |
| [F5](#f5--temporizador) | Descansos durante el entrenamiento | ⬜ |
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

**Objetivo:** poder usar Fit-Up a diario. Al terminar F1 la app ya sirve, aunque no tenga
calendario ni ranking.
**Criterio de aceptación:** registrar el entrenamiento de un martes desde el móvil el
domingo siguiente, en menos de 30 segundos.

### Backend
- [ ] Capa `application`: casos de uso `CrearRutina`, `EditarRutina` (nueva versión),
      `ObtenerDiaDeHoy`, `RegistrarEntrenamiento`, `ListarHistorial`
- [ ] Repositorios SQLite sobre objetos de dominio (no filas)
- [ ] API FastAPI con OpenAPI: rutinas, planificación semanal, sesiones, historial
- [ ] Registro **como planificado** en una sola llamada, con desviaciones opcionales
- [ ] Registro retroactivo con validación de fecha (pasado sí, futuro no)
- [ ] Peso corporal: registro y consulta
- [ ] Export JSON completo + backup automático diario *(M5, adelantado a F1: años de
      historial irreemplazable no pueden esperar a F7)*
- [ ] Token de acceso y binding configurable (`127.0.0.1` por defecto)

### Frontend
- [ ] Andamiaje React + TypeScript + Vite, PWA instalable, tema oscuro
- [ ] Generación de tipos TS desde OpenAPI
- [ ] Pantalla **Hoy**: rutina del día + botón "✓ Hice esta rutina"
- [ ] Sección "Pendientes de registrar" resoluble en un toque
- [ ] Editor de rutinas: ejercicios, series, reps, peso, descansos
- [ ] Organización de la semana
- [ ] Vista de entrenamiento: alto contraste, check por serie
- [ ] Historial navegable

### Decisiones abiertas de F1
- Campo RIR/RPE opcional por serie *(recomendado: sí, es lo que hace segura la progresión
  de F3)*
- Estado `partial` en la UI de registro *(recomendado: sí)*

---

## F2 · Calendario y cumplimiento

**Objetivo:** ver de un vistazo qué se cumplió y qué no, sin que la app mienta sobre lo
que aún no has registrado.

- [ ] `ObtenerCalendario(mes)` resolviendo los 7 estados del día
- [ ] Vista mensual navegable, con **color + icono** (nunca solo color)
- [ ] Detalle del día: planificado vs realizado, acciones disponibles
- [ ] Registrar excepciones (descanso, lesión, viaje, movido)
- [ ] Registro retroactivo desde el calendario, prellenado con lo planificado
- [ ] Métrica de adherencia excluyendo `PENDING`
- [ ] Ventana de gracia configurable en ajustes

---

## F3 · Progresión

**Objetivo:** el botón "Progresar" del enunciado, sin que pueda subir la dificultad de
forma irresponsable.

- [ ] `EvaluarProgresion` sobre todos los ejercicios de una rutina
- [ ] `AplicarProgresion`: nueva versión + `progression_event`, transaccional
- [ ] Deshacer una progresión (nueva versión que revierte; nunca se borra historia)
- [ ] UI: badge "listo para progresar", preview del diff, confirmación
- [ ] Mostrar `UNDETERMINED` con su motivo, sin ocultarlo
- [ ] Editor de reglas por ejercicio
- [ ] Deload sugerido tras regresiones *(M3)*
- [ ] Cadena de variantes para calistenia en la UI *(M8)*

---

## F4 · Métricas y ranking muscular

**Objetivo:** la característica visual insignia.

- [ ] Servicio de métricas: volumen, frecuencia, e1RM, evolución por ejercicio y músculo
- [ ] Aplanado historial → `StimulusEvent` por músculo
- [ ] SVG del cuerpo (frontal y dorsal) con `svg_key` por grupo muscular
- [ ] Colores por tier + halo de actividad
- [ ] Ficha de músculo: score, factores, ejercicios, histórico, qué falta para el siguiente tier
- [ ] `muscle_score_snapshot` semanal, reconstruible
- [ ] Calibración de `reference_ratio` por músculo con datos reales
- [ ] Avisos de equilibrio empuje/tirón y cuádriceps/femoral *(M7)*

**Riesgo principal:** la calibración de los umbrales. Hasta tener meses de historial real,
los rangos son provisionales y así deben presentarse.

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
| M3 | Deload sugerido | F3 |
| M4 | Bandeja de propuestas | F6 (diferida) |
| M5 | Export/import JSON + backup automático | F1 |
| M6 | Estado "Sin datos" ≠ Iron | F0 ✅ |
| M7 | Avisos de equilibrio muscular | F4 |
| M8 | Cadena de variantes para calistenia | F0 ✅ (motor) / F3 (UI) |
| M9 | Estado `partial` de sesión | F0 ✅ (esquema) / F1 (UI) |
| M10 | Ciclos rotativos A/B/C | Sin programar; el esquema lo contempla |

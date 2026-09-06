# Fit-Up

Aplicación personal de **registro, planificación y progresión de entrenamiento**, con ranking
muscular visual y preparada para ser operada por un agente de IA local.

> **Estado actual: FASE 0 — Diseño.** No hay código de aplicación todavía.
> El diseño se cierra cuando se resuelvan las decisiones abiertas.

## Documentación

| Documento | Contenido |
|---|---|
| [docs/00-analisis-y-arquitectura.md](docs/00-analisis-y-arquitectura.md) | Análisis completo: dominio, reglas, arquitectura, progresión, ranking, IA, riesgos, roadmap |
| [docs/01-decisiones-pendientes.md](docs/01-decisiones-pendientes.md) | Decisiones que requieren aprobación humana (bloqueantes) |
| [docs/adr/](docs/adr/) | Architecture Decision Records (se llenan al resolver cada decisión) |

## Principios

1. **Plan ≠ Historial.** La rutina es lo planificado; el historial es lo realmente realizado. Nunca se mezclan.
2. **Lo derivable se calcula, no se almacena** (salvo snapshots explícitamente marcados como caché reconstruible).
3. **El dominio es puro y determinista.** Progresión, ranking y cumplimiento son funciones sin I/O ni reloj implícito.
4. **Un solo núcleo, varios adaptadores.** UI y agente de IA consumen los mismos casos de uso: no hay lógica duplicada ni caminos que salten las reglas.
5. **Si el sistema no puede determinar algo con seguridad, lo dice.** No inventa progresiones ni métricas.
6. **Sin sobreingeniería.** Sin nube, sin multiusuario, sin dependencias que no paguen su coste.

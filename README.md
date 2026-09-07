# Fit-Up

Aplicación personal de **registro, planificación y progresión de entrenamiento**, con ranking
muscular visual y preparada para ser operada por un agente de IA local.

> **Estado: F0 y F1 completadas.** La app ya sirve para registrar entrenamientos a diario.
> Siguiente: F2 — calendario mensual.

## Arranque rápido

```bash
cd backend && python -m pip install -e ".[dev]" && python -m fitup.cli init
cd ../frontend && npm install && npm run build
cd ../backend && python -m fitup.cli serve
```

Abre `http://127.0.0.1:8000`. Para usarla desde el móvil en tu WiFi:

```bash
python -m fitup.cli serve --lan
```

Muestra un token; pégalo en **Ajustes → Acceso desde el móvil**.

## Documentación

| Documento | Contenido |
|---|---|
| [docs/00-analisis-y-arquitectura.md](docs/00-analisis-y-arquitectura.md) | Análisis completo: dominio, reglas, arquitectura, progresión, ranking, IA, riesgos, roadmap |
| [docs/01-decisiones-pendientes.md](docs/01-decisiones-pendientes.md) | Registro de decisiones: cerradas, defaults aplicados y abiertas |
| [docs/02-plan-de-implementacion.md](docs/02-plan-de-implementacion.md) | Plan por fases con seguimiento de hitos |
| [CLAUDE.md](CLAUDE.md) | Guía de trabajo: comandos, invariantes y convenciones |

## Estructura

```
backend/    Python · dominio puro + aplicación + API FastAPI + SQLite
frontend/   React + TypeScript · PWA, tipos generados desde OpenAPI
docs/       Análisis, decisiones (ADR) y plan de implementación
```
| [docs/adr/](docs/adr/) | Architecture Decision Records: distribución, stack, ranking, integración con IA |

## Decisiones estructurales

- **Distribución:** servidor local en el PC + PWA accesible desde el móvil por LAN.
- **Stack:** Python + FastAPI + SQLite · React + TypeScript · tipos TS generados desde OpenAPI.
- **Ranking:** el rango Iron→Radiant mide **desarrollo**; la actividad reciente es un indicador secundario.
- **Agente de IA:** proyecto externo y autónomo. Fit-Up ofrece un contrato estable (OpenAPI + MCP) y protege el historial con **inmutabilidad, auditoría y backups**, no con permisos.

## Principios

1. **Plan ≠ Historial.** La rutina es lo planificado; el historial es lo realmente realizado. Nunca se mezclan.
2. **Lo derivable se calcula, no se almacena** (salvo snapshots explícitamente marcados como caché reconstruible).
3. **El dominio es puro y determinista.** Progresión, ranking y cumplimiento son funciones sin I/O ni reloj implícito.
4. **Un solo núcleo, varios adaptadores.** UI y agente de IA consumen los mismos casos de uso: no hay lógica duplicada ni caminos que salten las reglas.
5. **Si el sistema no puede determinar algo con seguridad, lo dice.** No inventa progresiones ni métricas.
6. **Sin sobreingeniería.** Sin nube, sin multiusuario, sin dependencias que no paguen su coste.

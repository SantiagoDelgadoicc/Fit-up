# Decisiones

## Cerradas

| # | Decisión | Resultado | ADR |
|---|---|---|---|
| D1 | Forma de distribución | App web local (servidor en PC) + PWA accesible desde el móvil por LAN | [ADR-0001](adr/0001-distribucion-web-local-pwa.md) |
| D2 | Stack principal | Python + FastAPI + SQLite; React + TypeScript (PWA); tipos TS generados desde OpenAPI | [ADR-0002](adr/0002-stack-python-react.md) |
| D3 | Significado del rango muscular | Rango = Desarrollo/Capacidad; Actividad como halo secundario; umbrales absolutos editables | [ADR-0003](adr/0003-ranking-desarrollo-con-halo-actividad.md) |
| D4 | Integración con la IA | Replanteada: el agente es un proyecto externo y autónomo. Protección por reversibilidad y auditoría, no por permisos | [ADR-0004](adr/0004-integracion-con-agente-externo-autonomo.md) |

## Defaults aplicados (revocables en cualquier momento)

| # | Tema | Default |
|---|---|---|
| d5 | Planificación | Semana fija (lunes–domingo), esquema preparado para ciclos rotativos |
| d6 | Ventana de gracia antes de marcar 🔴 | 3 días |
| d7 | Series planificadas | Filas explícitas (3×15 = 3 filas), generadas por la UI |
| d8 | Unidades | Kilogramos |
| d9 | Base de datos | SQLite con migraciones versionadas, WAL activado |
| d10 | RIR/RPE por serie | Campo opcional presente desde F1 |
| d11 | Músculo sin ejercicios | Estado "Sin datos", no Iron |
| d12 | Sesión parcial | Estado `partial` soportado desde F1 |
| d13 | Backup | Copia diaria automática + export JSON |
| d14 | Tema | Oscuro por defecto |
| d15 | Fechas futuras | Prohibido registrar en el futuro |

## Abiertas

| # | Tema | Cuándo se decide |
|---|---|---|
| D5 | ¿Bandeja de propuestas para el agente (`AgentProposal`)? | F6, con historial real y el agente en funcionamiento |
| D6 | ¿Registro offline desde el móvil con cola y sincronización? | F7, si el uso real lo justifica |
| D7 | ¿Ciclos rotativos A/B/C además de semana fija? | Cuando lo necesites; el esquema ya lo contempla |

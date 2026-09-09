# Architecture Decision Records

Un fichero por decisión cerrada: `NNNN-titulo.md`.

Plantilla: **Contexto → Decisión → Alternativas descartadas → Consecuencias → Estado**.

Las decisiones abiertas y los defaults aplicados viven en
[../01-decisiones-pendientes.md](../01-decisiones-pendientes.md). Cómo se materializa la
0004 en la práctica, en [../03-contrato-del-agente.md](../03-contrato-del-agente.md).

| ADR | Decisión |
|---|---|
| [0001](0001-distribucion-web-local-pwa.md) | Servidor local en el PC + PWA accesible desde el móvil por LAN |
| [0002](0002-stack-python-react.md) | Python + FastAPI + SQLite · React + TypeScript · tipos generados desde OpenAPI |
| [0003](0003-ranking-desarrollo-con-halo-actividad.md) | El rango muscular mide **desarrollo**; la actividad es un halo secundario |
| [0004](0004-integracion-con-agente-externo-autonomo.md) | El agente de IA es externo y autónomo: protección por reversibilidad y auditoría, no por permisos |
| [0005](0005-el-pc-es-la-superficie-principal.md) | El **PC** es la superficie principal; el móvil, la secundaria |

Un ADR aceptado no se reescribe: si cambia la decisión, se añade otro que lo reemplace o
lo matice, y se dice cuál.

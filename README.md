# Fit-Up

Aplicación personal de **registro, planificación y progresión de entrenamiento**, con ranking
muscular visual y preparada para ser operada por un agente de IA local.

> **Estado: en pruebas y pulido.** F0–F6 completadas. La app se usa a diario:
> registrar entrenamientos, revisar el cumplimiento del mes, aplicar sobrecarga progresiva
> —con su motivo a la vista y siempre reversible—, ver el ranking muscular sobre un mapa
> corporal y cronometrar los descansos. El agente de IA externo tiene su superficie
> completa: servidor MCP, permisos, auditoría y copias previas.
>
> **Qué significa "en pruebas":** la funcionalidad está completa y probada, pero lleva
> poco tiempo en uso real. Se esperan asperezas de interfaz y ajustes de calibración. En
> particular, **el rango muscular es una estimación provisional** (D9): sirve para
> compararte contigo mismo, no con nadie más. Nada de esto pone en riesgo el historial:
> es inmutable, versionado, auditado y con copia diaria.

## Arranque rápido

```bash
cd backend && python -m pip install -e ".[dev]" && python -m fitup.cli init
cd ../frontend && npm install && npm run build
cd ../backend && python -m fitup.cli serve
```

Abre `http://127.0.0.1:8000`.

### Acceso directo en Windows

Para no repetir eso cada día:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\crear-accesos-directos.ps1 -Imagen "C:
uta	u\icono.png"
```

Crea **Fit-Up** en el escritorio y en la carpeta del proyecto. Doble clic arranca el
servidor y abre el navegador solo; cerrar la ventana lo para.

Los accesos apuntan a [`scripts/Fit-Up.bat`](scripts/Fit-Up.bat), que vive en el
repositorio: actualizar la app es un `git pull` y no hay que rehacerlos. El icono se
convierte y se guarda en `local/`, fuera de control de versiones — cada equipo genera el
suyo a partir de la imagen que quiera.

### Para el agente de IA

```bash
cd backend && python -m fitup.cli mcp
```

Servidor MCP por stdio, con 16 herramientas. Un agente lo conecta y descubre lo que puede
hacer; por defecto lee y propone, pero no escribe. Los permisos se activan en
**Ajustes → Permisos del agente**. Contrato completo en
[docs/03-contrato-del-agente.md](docs/03-contrato-del-agente.md).

### Desde el móvil

Para usarla desde el móvil en tu WiFi:

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
| [docs/03-contrato-del-agente.md](docs/03-contrato-del-agente.md) | Cómo debe interactuar un agente de IA externo: actor, permisos, auditoría y límites |
| [licenses/](licenses/) | Material de terceros y sus licencias |
| [CLAUDE.md](CLAUDE.md) | Guía de trabajo: comandos, invariantes y convenciones |

## Estructura

```
backend/    Python · dominio puro + aplicación + API FastAPI + SQLite
frontend/   React + TypeScript · PWA, tipos generados desde OpenAPI
docs/       Análisis, decisiones (ADR) y plan de implementación
```
| [docs/adr/](docs/adr/) | Architecture Decision Records: distribución, stack, ranking, IA, superficie principal |

## Decisiones estructurales

- **Distribución:** servidor local en el PC + PWA accesible desde el móvil por LAN.
- **Superficie principal:** el PC. El móvil es el segundo escenario, para el gimnasio.
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

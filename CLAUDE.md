# CLAUDE.md

Guía para trabajar en Fit-Up. Léela antes de tocar código.

## Qué es

App **personal, monousuario, local-first** de planificación, registro y progresión de
entrenamiento, con ranking muscular visual y preparada para ser operada por un agente de
IA local. Sin nube, sin multiusuario, sin cuentas.

**Fase actual: F0 y F1 completadas.** Hay dominio, esquema, catálogo, API HTTP y PWA:
la app ya se usa a diario. Siguiente F2 (calendario). Ver
[docs/02-plan-de-implementacion.md](docs/02-plan-de-implementacion.md).

## Idioma

**Habla siempre en español** con el usuario. El código, los comentarios, los nombres de
dominio, los mensajes de commit y la documentación también van en español. Se admite
terminología técnica inglesa cuando es estándar (`commit`, `endpoint`, `deploy`).

Sé conciso y denso: pocas palabras, suficiente profundidad. No repitas contexto ya conocido.

## Comandos

Backend (desde `backend/`):

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m pytest --cov --cov-report=term-missing
python -m ruff check . && python -m ruff format .
python -m fitup.cli init            # crear/actualizar BD y sembrar catálogo
python -m fitup.cli check           # integridad + coherencia del catálogo
python -m fitup.cli serve           # API + PWA en 127.0.0.1:8000
python -m fitup.cli serve --lan     # accesible desde el móvil, con token
python -m fitup.cli export          # volcado JSON
```

Frontend (desde `frontend/`):

```bash
npm install
npm run dev          # Vite con proxy a la API en :8000
npm run typecheck
npm run build        # a dist/, que el backend sirve solo
npm run gen:api      # regenerar tipos desde backend/openapi.json
```

**Si cambias la API**, regenera el contrato o CI fallará:

```bash
cd backend && python -c "import json;from pathlib import Path;from fitup.api.app import create_app;from fitup.api.deps import Settings;Path('openapi.json').write_text(json.dumps(create_app(Settings(db_path=Path('data/fitup.db'),token=None,require_token=False)).openapi(),ensure_ascii=False,indent=2),encoding='utf-8')"
cd ../frontend && npm run gen:api
```

CI ejecuta lint, formato, tests, cobertura mínima del 90 % en `domain/` y en
`application/`+`api/`, sincronía del OpenAPI, arranque de extremo a extremo, y typecheck
y build del frontend.

## Arquitectura

```
backend/src/fitup/
  domain/           PURO: sin I/O, sin reloj, sin BD. Aquí vive el riesgo del proyecto.
    enums.py        vocabulario; sus valores coinciden con los CHECK del SQL
    models.py       entidades inmutables (frozen dataclasses)
    metrics/load.py normalización de carga a kg equivalentes, volumen, e1RM
    compliance/     máquina de estados del día (7 estados)
    progression/    motor de sobrecarga progresiva
    ranking/        tiers + fórmula v1 (versionada)
  infrastructure/
    db/             conexión, migrador, migrations/*.sql
    seed/           catálogo JSON + cargador idempotente
  api/            adaptador HTTP: schemas, routers, mappers, deps
  cli.py

frontend/src/
  api/            client.ts (fetch tipado) · hooks.ts (react-query) · schema.d.ts (GENERADO)
  components/     primitivas compartidas
  pages/          Hoy · Rutinas · RoutineEditor · Semana · Historial · Ajustes
```

`schema.d.ts` se genera: **no lo edites a mano**.

### Invariantes que no se negocian

1. **El dominio es puro.** Sin acceso a BD, sin `datetime.now()`: la fecha se **inyecta**
   (`today=`). Si necesitas el reloj dentro de `domain/`, el diseño está mal.
2. **Plan ≠ historial.** `routine_*` es lo planificado, `workout_session*` lo realizado.
   Nunca se mezclan ni se derivan uno del otro.
3. **Las rutinas se versionan, no se mutan.** Editar crea `version_no + 1`. Una sesión
   histórica apunta a la versión concreta que se ejecutó. Nunca hagas `UPDATE` sobre
   `routine_exercise` o `planned_set` de una versión ya usada.
4. **Lo derivable se calcula.** Volumen, adherencia, e1RM y ranking no se almacenan. Única
   excepción: `muscle_score_snapshot`, caché reconstruible marcada con `formula_version`.
5. **Si no se puede determinar, se dice.** El motor devuelve `UNDETERMINED` con motivo;
   `load.py` lanza `LoadUndeterminable`; `adherence()` devuelve `None`, no `0`. **Nunca
   rellenes un hueco con una suposición por defecto.**
6. **Un solo núcleo, varios adaptadores.** API y agente MCP consumirán los mismos casos de
   uso. No dupliques lógica ni abras un camino que salte las reglas de negocio.
7. **Fecha local ISO** (`YYYY-MM-DD`) para el "día de entrenamiento". Nunca UTC. Los
   instantes de auditoría (`logged_at`, `ts`) sí llevan offset.

### Migraciones

`infrastructure/db/migrations/NNNN_nombre.sql`, aplicadas en orden y con checksum
verificado. **Nunca edites una migración ya aplicada**: crea la siguiente. El migrador
falla ruidosamente si detectas lo contrario, y ese fallo es correcto.

### Catálogo

`infrastructure/seed/data/*.json`. Al añadir un ejercicio: slug único, músculos con rol
válido, `load_factor` obligatorio si `load_type` es `corporal`, y `next_variant` sin
ciclos. `catalog.validate()` lo comprueba y los tests de `test_schema.py` lo blindan.

## Estilo

- Comentarios que expliquen **por qué**, no qué. Si el comentario reformula el código, sobra.
- Los tests documentan el comportamiento esperado: nombres descriptivos en español y
  docstring cuando el caso encierra una decisión de diseño.
- Sin dependencias nuevas salvo que sustituyan código que habría que mantener. Las que hay
  pasaron ese filtro: FastAPI/pydantic/uvicorn en el backend; react, react-router y
  react-query en el frontend. El **dominio no depende de ninguna**, y eso no cambia.
- Ruff con `line-length = 100`. `N812`, `N818` y `B008` están ignoradas a propósito, con el
  motivo documentado en `pyproject.toml`.
- El frontend usa CSS plano con variables: cinco pantallas no justifican un framework.

## Decisiones cerradas

Los cuatro ADR de [docs/adr/](docs/adr/) son vinculantes:

| ADR | Decisión |
|---|---|
| 0001 | Servidor local en el PC + PWA accesible desde el móvil por LAN |
| 0002 | Python + FastAPI + SQLite · React + TypeScript · tipos TS generados desde OpenAPI |
| 0003 | El rango mide **desarrollo**; la actividad es un halo secundario |
| 0004 | El agente de IA es **externo y autónomo**: la protección es reversibilidad y auditoría, no permisos |

Sobre 0004, un matiz que condiciona el diseño: los scopes del agente son un guardarraíl
**contra errores**, no una frontera de seguridad — un proceso con control del PC puede
saltárselos. Lo que protege el historial de verdad es inmutabilidad, `AuditLog`, deshacer
y backups. No escribas código que dé por supuesto lo contrario.

## Control humano

Puedes decidir por tu cuenta cambios locales, mecánicos, reversibles y de bajo riesgo.

**Consulta antes de decidir sobre:** arquitectura · esquema de base de datos · tecnologías
principales · contratos y API · seguridad · permisos · estructura del dominio ·
integraciones · cambios difíciles de revertir · cambios importantes de UX · deuda técnica
significativa.

Cuando haya un dilema real, preséntalo así y **no avances hasta que se resuelva**:

```
HUMAN DECISION REQUIRED
Problema: ...
Opción A: significado + pros + contras + riesgos.
Opción B: significado + pros + contras + riesgos.
Recomendación: ...
Impacto: ...
Decisión requerida: ...
```

Si detectas una mejora significativa, propónla con su porqué y su impacto; no la incorpores
sola si es importante.

## Nunca

- Versionar `data/`, `*.db` o cualquier historial de entrenamiento.
- Almacenar como dato permanente algo derivable del historial.
- Inventar una progresión, una carga o una métrica cuando faltan datos.
- Mutar una versión de rutina ya referenciada por el historial.
- Añadir una tecnología porque sea popular.

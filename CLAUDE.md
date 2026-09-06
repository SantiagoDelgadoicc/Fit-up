# CLAUDE.md

Guía para trabajar en Fit-Up. Léela antes de tocar código.

## Qué es

App **personal, monousuario, local-first** de planificación, registro y progresión de
entrenamiento, con ranking muscular visual y preparada para ser operada por un agente de
IA local. Sin nube, sin multiusuario, sin cuentas.

**Fase actual: F0 completada.** Existen dominio, esquema, catálogo y CI. No existen
todavía API ni frontend. Ver [docs/02-plan-de-implementacion.md](docs/02-plan-de-implementacion.md).

## Idioma

**Habla siempre en español** con el usuario. El código, los comentarios, los nombres de
dominio, los mensajes de commit y la documentación también van en español. Se admite
terminología técnica inglesa cuando es estándar (`commit`, `endpoint`, `deploy`).

Sé conciso y denso: pocas palabras, suficiente profundidad. No repitas contexto ya conocido.

## Comandos

Todo se ejecuta desde `backend/`.

```bash
python -m pip install -e ".[dev]"        # instalar
python -m pytest                          # tests
python -m pytest --cov --cov-report=term-missing
python -m ruff check . && python -m ruff format .
python -m fitup.cli --db ../data/fitup.db init    # crear/actualizar BD y sembrar catálogo
python -m fitup.cli --db ../data/fitup.db check   # integridad + coherencia del catálogo
```

CI ejecuta lint, formato, tests, un mínimo del 90 % de cobertura en `domain/` y un arranque
de extremo a extremo. Si tocas `domain/`, la cobertura es un requisito, no una aspiración.

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
  cli.py
```

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
- Sin dependencias nuevas salvo que sustituyan código que habría que mantener. F0 no tiene
  ninguna en producción, y eso es deliberado.
- Ruff con `line-length = 100`. `N812` y `N818` están ignoradas a propósito (ver pyproject).

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

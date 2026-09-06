# ADR-0004 — Integración con un agente externo autónomo

**Estado:** Aceptada (2026-09-06) · **Reemplaza a:** D4 (replanteada)

## Contexto
El agente de IA **no es un componente de Fit-Up**: es un proyecto independiente que se ejecuta en el mismo PC con autonomía total sobre la máquina.

De ahí se sigue un hecho que condiciona todo el diseño: **los permisos de Fit-Up no son una frontera de seguridad frente a ese agente.** Un proceso con control del sistema puede abrir `fitup.db` directamente, editar el fichero de configuración de scopes o detener el servidor. Diseñar scopes como si contuvieran a ese agente sería teatro de seguridad.

Por tanto, el objetivo de la integración deja de ser *impedir* y pasa a ser:
1. ofrecer un **camino sancionado** más cómodo y fiable que tocar la base de datos a mano, para que el agente lo use por conveniencia, no por obligación;
2. garantizar que **cualquier cosa que haga sea visible y reversible**.

## Decisión

### 1. Contrato explícito y estable
Fit-Up expone dos superficies sobre **los mismos casos de uso**: **HTTP + OpenAPI** y un **servidor MCP**. Ambas aplican las reglas de negocio, validan la entrada y son idempotentes. El esquema de la BD se considera **detalle interno**: la interfaz soportada es la API.

### 2. La protección es reversibilidad y auditoría, no prevención
- `actor` (`usuario` | `agente` | `sistema`) obligatorio en **toda** escritura.
- Rutinas en **versiones inmutables**: ninguna escritura destruye el plan anterior.
- **Deshacer** disponible para toda progresión y todo cambio de rutina.
- `AuditLog` completo: acción, payload, resultado, timestamp.
- **Backup automático** diario y **antes de cualquier lote de escrituras del agente**; export JSON completo.
- Verificación de integridad de la BD al arrancar.

### 3. Los scopes se mantienen como guardarraíl contra errores
Configuración local con default `read` + `propose`; escrituras sensibles desactivadas. **Se documenta explícitamente que esto protege contra equivocaciones del agente, no contra un agente hostil.** Es barato y evita la clase de fallo más probable: un modelo confundido escribiendo historial falso.

### 4. Acceso concurrente a SQLite
WAL activado y `busy_timeout` configurado, de modo que un segundo proceso leyendo el fichero no rompa nada. El contrato documentado es **"usa la API, no el fichero"**, pero el sistema debe sobrevivir a que no se cumpla.

### 5. El token de LAN sí es una frontera real
Derivado de ADR-0001, el servidor queda expuesto en la red doméstica. El token protege frente a **otros dispositivos de la red** — ahí sí es una frontera genuina, a diferencia de los scopes frente al agente local.

### 6. Frontera datos/instrucciones
El contenido almacenado (notas, nombres de ejercicios, descripciones) es **dato, nunca instrucción**. Se documenta en el export y en las descripciones de las tools MCP, para que el agente no interprete como órdenes textos que provienen de la base de datos.

## Consecuencias
- La seguridad del historial descansa en **backups, inmutabilidad y auditoría**, no en control de acceso. Es la postura honesta dado el modelo de amenaza real.
- Fit-Up no se acopla a ninguna IA concreta: MCP y OpenAPI son agnósticos de modelo.
- El export JSON documentado permite al agente analizar sin depender del proceso vivo.

## Diferido a F6
Si se construye o no una **bandeja de propuestas** (`AgentProposal`: el agente sugiere, el usuario aprueba en la UI). Con un agente autónomo puede ser ceremonia innecesaria, o puede ser justo el punto de control que se quiere conservar para los cambios de rutina. Se decide cuando exista historial real y el agente esté en funcionamiento; el diseño lo soporta sin refactor.

# ADR-0003 — El rango muscular representa Desarrollo; la Actividad es indicador secundario

**Estado:** Aceptada (2026-09-06) · **Reemplaza a:** D3

## Contexto
Cantidad de entrenamiento y desarrollo muscular no son equivalentes. Un rango que midiera actividad reciente se desplomaría tras una semana de descanso y empujaría a entrenar por el color en lugar de por el plan.

## Decisión
- **Rango Iron → Radiant = DESARROLLO / CAPACIDAD.** Métrica lenta, con trinquete, basada en las mejores marcas normalizadas (e1RM-equivalente) de los ejercicios que contribuyen a cada músculo.
- **Actividad reciente = indicador secundario** (halo o aro sobre el músculo en el mapa corporal): verde si hubo estímulo esta semana, gris si lleva tiempo sin entrenarse.
- **Umbrales absolutos** anclados al peso corporal, **editables** en configuración.
- **`bonus_progresión`**: aplicar sobrecarga progresiva eleva el score, de modo que el rango sube al progresar y no solo al acumular volumen.
- **`decay` con suelo**: nunca se pierde más de 1 tier respecto al pico en 8 semanas. El descanso no se castiga.
- **Estado "Sin datos"** (gris) para músculos sin ningún ejercicio asociado. No es Iron: "no medido" y "débil" son cosas distintas.
- **Explicabilidad obligatoria**: cada músculo muestra score, los factores que más aportan, ejercicios contribuyentes, histórico y qué falta para el siguiente tier.
- **Fórmula versionada** (`formula_version`) en módulo puro; los snapshots guardan la versión con la que fueron calculados y todo es recalculable desde el registro crudo.

## Alternativas descartadas
- **Rango = carga/actividad reciente:** feedback inmediato, pero volátil, castiga el descanso e incentiva sobreentrenar.
- **Dos rangos separados:** más honesto pero duplica la interfaz y diluye la característica visual insignia.

## Consecuencias
- El rango se mueve despacio: menos gratificación semanal, a cambio de significar algo. El halo de actividad cubre la necesidad de feedback inmediato.
- Requiere `peso_corporal` (con historial) y `load_factor` por ejercicio para normalizar calistenia e isométricos a kg-equivalentes.
- Los umbrales absolutos requieren una tabla de referencia curada, que se documenta como **aproximación editable**, nunca como verdad objetiva.
- Los tests del ranking son golden tests con fixtures versionados por `formula_version`.

## Actualización (2026-09-08) — cómo se mide el Desarrollo, fórmula v2

La decisión de fondo **no cambia**: el rango sigue siendo Desarrollo, la Actividad sigue
siendo el halo, y la fórmula sigue siendo versionada y pura. Lo que cambia es la forma de
medir el Desarrollo, y la propia ADR ya lo contemplaba al versionar la fórmula.

**Qué falló en v1.** «Mejores marcas normalizadas (e1RM-equivalente)» daba por buena la
extrapolación de Epley fuera de su rango válido (~12 repeticiones). Con series largas de
calistenia —30 y 100 repeticiones— multiplicaba la carga por 2 y por 4,3, y tres músculos
alcanzaron Radiant con dos días de registro. El sistema medía resistencia y la presentaba
como fuerza.

**Qué se sustituye.**

- «Mejores marcas normalizadas (e1RM-equivalente)» → **mejor serie única del ejercicio, en
  sus propias unidades** (repeticiones o segundos), comparada con la escalera de ese
  ejercicio (`domain/ranking/standards.py`).
- «Umbrales absolutos anclados al peso corporal, editables en configuración» → **umbrales
  absolutos por ejercicio**, en el dominio. Dejan de ser editables desde ajustes: son
  calibración de la fórmula, viajan con `formula_version` y cambiarlos debe recalcular. Lo
  que sigue siendo editable es el objetivo de volumen semanal, que gobierna la Actividad.
- «`bonus_progresión`» → **el trinquete**. Progresar sube el rango porque mueve la marca en
  la escalera; no hace falta un término aparte que premie mejorar. Y una marca solo cuenta
  cuando se ha repetido en dos sesiones, el mismo criterio que el motor de progresión.
- Nuevo: **techo por ejercicio** (`max_tier`). Un ejercicio ligero no puede dar rango alto
  por muchas repeticiones que se acumulen.

**Consecuencia práctica.** El rango deja de requerir `peso_corporal`: sin él se pierde el
volumen —y por tanto el halo—, pero el mapa ya no queda en blanco. `load_factor` sigue
haciendo falta para el volumen y para valorar el lastre.

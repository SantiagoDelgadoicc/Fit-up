# Material de terceros

Fit-Up no depende de librerías externas más allá de las declaradas en
`backend/pyproject.toml` y `frontend/package.json`. Aquí se recogen los assets
copiados al repositorio, que viajan con su licencia.

| Asset | Origen | Licencia | Dónde vive |
|---|---|---|---|
| Trazados del mapa corporal | [MuscleMap](https://github.com/melihcolpan/MuscleMap), tag 1.6.4 | MIT — [MuscleMap-LICENSE.txt](MuscleMap-LICENSE.txt) | `frontend/src/components/bodyPaths.ts` |

## MuscleMap

Paquete SwiftUI del que solo se ha tomado la **geometría**: los `d` de los
trazados de la silueta masculina, frontal y dorsal, que en el original están en
`Sources/MuscleMap/Data/MaleFrontPaths.swift` y `MaleBackPaths.swift`. No se ha
copiado código.

Los trazados se conservan sin retocar. Lo único añadido al traerlos es la
correspondencia entre las zonas del asset y los `svg_key` del catálogo de
Fit-Up, documentada en la cabecera de `bodyPaths.ts` junto a las tres
decisiones que hubo que tomar (zonas descartadas, zonas recortadas y
composición de la silueta de fondo).

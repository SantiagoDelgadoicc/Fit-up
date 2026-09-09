# Material de terceros

Fit-Up no depende de librerías externas más allá de las declaradas en
`backend/pyproject.toml` y `frontend/package.json`. Aquí se recogen los assets
copiados al repositorio, que viajan con su licencia.

| Asset | Origen | Licencia | Dónde vive |
|---|---|---|---|
| Trazados del mapa corporal | [MuscleMap](https://github.com/melihcolpan/MuscleMap), tag 1.6.4 | MIT — [MuscleMap-LICENSE.txt](MuscleMap-LICENSE.txt) | `frontend/src/components/bodyPaths.ts` |
| Tipografía Inter (variable) | [rsms/inter](https://github.com/rsms/inter), v20 vía Google Fonts | OFL 1.1 — [Inter-OFL.txt](Inter-OFL.txt) | `frontend/public/fonts/inter-*.woff2` |
| Tipografía Outfit (variable) | [Outfitio/Outfit-Fonts](https://github.com/Outfitio/Outfit-Fonts), v15 vía Google Fonts | OFL 1.1 — [Outfit-OFL.txt](Outfit-OFL.txt) | `frontend/public/fonts/outfit-*.woff2` |

## Tipografías

Se copian al repositorio en vez de enlazarlas a un CDN porque la app es
local-first (ADR-0001): con un `<link>` a Google Fonts, entrenar sin conexión
cambiaría la letra de toda la interfaz. Son los subconjuntos `latin` y
`latin-ext` de las versiones variables, 180 kB en total, sin modificar.

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

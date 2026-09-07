"""Calibración del ranking: qué marca corresponde al tope de la escala.

``reference_ratio`` es el 1RM equivalente —ya ponderado por el rol del músculo
en el ejercicio— que vale 100 puntos de desarrollo, expresado en múltiplos del
peso corporal. Es el parámetro que traduce "levanto X" a "estoy en tal rango",
y por tanto el que decide si la escalera tiene sentido.

**Estos valores son provisionales** (decisión D9, abierta hasta tener meses de
historial real). Se razonaron así:

1. Se partió de una marca de nivel élite amateur para el ejercicio principal de
   cada músculo (press banca ≈ 1.6× el peso corporal, sentadilla ≈ 2.2×,
   dominada lastrada ≈ 1.7×…).
2. Se **duplicó**. El tope de la escala no es "lo que hace un atleta muy
   bueno": es el techo de una escalera que debe tener recorrido durante años.
   Con la referencia puesta en la marca élite, un principiante aparecería en
   Platinum en su primer mes y el ranking dejaría de significar nada.

Con esta calibración, y a modo de orientación: un principiante cae en Iron o
Bronze, alguien con dos o tres años constantes ronda Gold o Platinum, un nivel
claramente avanzado alcanza Diamond o Ascendant, y Radiant queda fuera del
alcance de casi cualquiera. Ese reparto es el objetivo; los números concretos
se ajustarán cuando haya historial suficiente para comprobarlo.

Los valores se pueden sobrescribir sin tocar el código desde los ajustes
(ADR-0003: "umbrales absolutos, editables en configuración"): la capa de
aplicación mezcla esta tabla con lo que haya guardado el usuario.
"""

from __future__ import annotations

#: Múltiplos del peso corporal que valen 100 puntos de desarrollo.
REFERENCE_RATIO: dict[str, float] = {
    # --- Torso ---
    "pectoral": 3.0,
    "dorsal_ancho": 3.0,
    "trapecio": 4.0,
    "romboides": 2.4,
    "deltoide_anterior": 2.0,
    # Los deltoides laterales y posteriores solo se entrenan con cargas
    # pequeñas: su referencia no es comparable a la de un básico pesado.
    "deltoide_lateral": 0.6,
    "deltoide_posterior": 0.6,
    # --- Brazos ---
    # Bíceps y antebrazo cobran casi siempre de refilón, como secundarios de
    # dominadas y peso muerto. Con una referencia baja, media marca de un
    # básico pesado los disparaba a Radiant sin haberlos entrenado nunca
    # directamente: por eso su referencia es alta pese a moverse poco peso.
    "biceps": 2.0,
    "triceps": 2.2,
    "antebrazo": 2.5,
    # --- Piernas ---
    # Isquiotibiales, glúteo y lumbares son primarios en el peso muerto, que
    # es la marca más alta de cualquier registro: su referencia va acorde.
    "cuadriceps": 4.0,
    "isquiotibiales": 5.0,
    "gluteo": 5.0,
    "aductores": 3.0,
    "gemelos": 4.0,
    # --- Core ---
    # Isométricos en su mayoría: la equivalencia tiempo→repeticiones ya los
    # penaliza (ISOMETRIC_FACTOR), así que la referencia es moderada.
    "abdominales": 2.5,
    "oblicuos": 2.0,
    "lumbares": 5.0,
}

#: Para un músculo sin referencia propia. Conservador a propósito: es mejor
#: que un músculo nuevo del catálogo puntúe bajo a que regale un rango alto.
DEFAULT_REFERENCE_RATIO = 2.5

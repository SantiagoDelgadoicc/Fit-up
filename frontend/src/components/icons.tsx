/**
 * Iconos de la interfaz.
 *
 * Trazados propios, no una librería: son veintitantos símbolos y una
 * dependencia de iconos pesa más de lo que ahorra (y arrastra un sistema de
 * nombres que no es el nuestro).
 *
 * Antes esto eran emojis. Se cambiaron por dos motivos, y el segundo importa
 * más que el primero:
 *
 * 1. Cada sistema operativo dibuja los emojis a su manera, con su propio
 *    color y su propio peso. La barra lateral se veía distinta en el PC y en
 *    el móvil, y ninguno de los dos coincidía con la paleta del tema.
 * 2. **Los estados del día se distinguían solo por color.** 🟢🟡🟠🔴 son el
 *    mismo círculo pintado siete veces; la regla de la casa es que un estado
 *    nunca se comunica solo por color, y aquella no la cumplía. Aquí cada
 *    estado tiene su propia forma —marca, media luna, aspa, guion— y se lee
 *    igual en escala de grises.
 *
 * Todos comparten rejilla de 24, `currentColor` y grosor 1.75: heredan el
 * color de donde estén y el tamaño se fija desde el CSS, nunca aquí.
 */

import type { ReactNode, SVGProps } from "react";

export type IconName =
  // Navegación
  | "hoy"
  | "calendario"
  | "cuerpo"
  | "descanso"
  | "rutinas"
  | "semana"
  | "historial"
  | "ajustes"
  // Estados del día
  | "estado-cumplida"
  | "estado-parcial"
  | "estado-pendiente"
  | "estado-fallada"
  | "estado-descanso"
  | "estado-extra"
  | "estado-excusado"
  // Veredictos de la progresión
  | "sube"
  | "espera"
  | "duda"
  | "baja"
  // Acciones
  | "marca"
  | "reproducir"
  | "pausa"
  | "reiniciar"
  | "cerrar"
  | "mas"
  | "campana"
  | "flecha-izquierda"
  | "flecha-derecha"
  | "flecha-arriba"
  | "flecha-abajo"
  | "desplegar"
  // Ilustración de estados vacíos
  | "luna"
  | "grafica"
  | "puntero";

/** Cada icono es solo su contenido: el `<svg>` lo pone el componente. */
const PATHS: Record<IconName, ReactNode> = {
  hoy: (
    <>
      <rect x="2.4" y="9.1" width="3.4" height="5.8" rx="1.3" />
      <rect x="18.2" y="9.1" width="3.4" height="5.8" rx="1.3" />
      <rect x="5.9" y="6.4" width="3.5" height="11.2" rx="1.4" />
      <rect x="14.6" y="6.4" width="3.5" height="11.2" rx="1.4" />
      <path d="M9.4 12h5.2" />
    </>
  ),
  calendario: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="3" />
      <path d="M8 2.8v4.4M16 2.8v4.4M3 10h18" />
    </>
  ),
  cuerpo: (
    <>
      <circle cx="12" cy="6.2" r="3.2" />
      <path d="M4.8 21a7.2 7.2 0 0 1 14.4 0" />
    </>
  ),
  descanso: (
    <>
      <circle cx="12" cy="13.8" r="7.7" />
      <path d="M12 9.8v4l2.4 1.6M9.4 2.6h5.2M12 2.6v3.5" />
    </>
  ),
  rutinas: (
    <>
      <path d="M9.2 4.2H7.6A2.6 2.6 0 0 0 5 6.8v11.8A2.6 2.6 0 0 0 7.6 21.2h8.8a2.6 2.6 0 0 0 2.6-2.6V6.8a2.6 2.6 0 0 0-2.6-2.6h-1.6" />
      <rect x="9.2" y="2.6" width="5.6" height="3.2" rx="1.2" />
      <path d="M8.6 11.2h6.8M8.6 15.2h4.4" />
    </>
  ),
  semana: (
    <>
      <rect x="2.8" y="5.5" width="18.4" height="13" rx="2.6" />
      <path d="M8.9 5.5v13M15.1 5.5v13" />
    </>
  ),
  historial: (
    <>
      <path d="M3.4 12a8.6 8.6 0 1 0 2.7-6.3" />
      <path d="M2.8 3.6v4.8h4.8" />
      <path d="M12 7.6V12l3 1.9" />
    </>
  ),
  ajustes: (
    <>
      <path d="M6 21v-6.4M6 10.6V3M12 21v-9.2M12 7.8V3M18 21v-4.6M18 12.6V3" />
      <path d="M3.4 14.6h5.2M9.4 7.8h5.2M15.4 16.4h5.2" />
    </>
  ),

  /* Estados: mismo círculo, marca distinta. La forma es la que informa. */
  "estado-cumplida": (
    <>
      <circle cx="12" cy="12" r="8.8" />
      <path d="m8.4 12.3 2.5 2.5 4.7-5.1" />
    </>
  ),
  "estado-parcial": (
    <>
      <circle cx="12" cy="12" r="8.8" />
      <path d="M12 3.2a8.8 8.8 0 0 1 0 17.6Z" fill="currentColor" stroke="none" />
    </>
  ),
  "estado-pendiente": <circle cx="12" cy="12" r="8.8" strokeDasharray="3 3.4" />,
  "estado-fallada": (
    <>
      <circle cx="12" cy="12" r="8.8" />
      <path d="m9.1 9.1 5.8 5.8M14.9 9.1l-5.8 5.8" />
    </>
  ),
  "estado-descanso": (
    <>
      <circle cx="12" cy="12" r="8.8" />
      <path d="M8.4 12h7.2" />
    </>
  ),
  "estado-extra": (
    <>
      <circle cx="12" cy="12" r="8.8" />
      <path d="M12 8.4v7.2M8.4 12h7.2" />
    </>
  ),
  "estado-excusado": (
    <>
      <circle cx="12" cy="12" r="8.8" />
      <path d="m8.6 15.4 6.8-6.8" />
    </>
  ),

  sube: (
    <>
      <circle cx="12" cy="12" r="8.8" />
      <path d="M12 16.2V8.1M8.7 11.4 12 8.1l3.3 3.3" />
    </>
  ),
  espera: (
    <>
      <circle cx="12" cy="12" r="8.8" />
      <path d="M12 7.4V12l3.1 1.9" />
    </>
  ),
  duda: (
    <>
      <circle cx="12" cy="12" r="8.8" />
      <path d="M9.6 9.6a2.45 2.45 0 1 1 3.3 2.35c-.6.22-.9.75-.9 1.35v.4" />
      <path d="M12 16.7h.01" strokeWidth="2.2" />
    </>
  ),
  baja: (
    <>
      <circle cx="12" cy="12" r="8.8" />
      <path d="M12 7.8v8.1M8.7 12.6 12 15.9l3.3-3.3" />
    </>
  ),

  marca: <path d="m4.8 12.6 4.9 4.9L19.4 6.6" />,
  reproducir: <path d="M7.2 4.6 19.4 12 7.2 19.4Z" fill="currentColor" />,
  pausa: <path d="M8.8 4.8v14.4M15.2 4.8v14.4" strokeWidth="2.6" />,
  reiniciar: (
    <>
      <path d="M3.4 12a8.6 8.6 0 1 0 2.7-6.3" />
      <path d="M2.8 3.6v4.8h4.8" />
    </>
  ),
  cerrar: <path d="M6.2 6.2 17.8 17.8M17.8 6.2 6.2 17.8" />,
  mas: <path d="M12 5.2v13.6M5.2 12h13.6" />,
  campana: (
    <>
      <path d="M6.4 10.2a5.6 5.6 0 0 1 11.2 0c0 4.3 1.5 5.6 1.5 5.6H4.9s1.5-1.3 1.5-5.6Z" />
      <path d="M10.1 19.1a2.1 2.1 0 0 0 3.8 0" />
    </>
  ),
  "flecha-izquierda": <path d="M19 12H5.4M11.2 5.8 5 12l6.2 6.2" />,
  "flecha-derecha": <path d="M5 12h13.6M12.8 5.8 19 12l-6.2 6.2" />,
  "flecha-arriba": <path d="M12 19V5.4M5.8 11.6 12 5.4l6.2 6.2" />,
  "flecha-abajo": <path d="M12 5v13.6M5.8 12.4 12 18.6l6.2-6.2" />,
  desplegar: <path d="m6 9.2 6 6 6-6" />,

  luna: <path d="M20.2 14.7A8.7 8.7 0 0 1 9.3 3.8a8.7 8.7 0 1 0 10.9 10.9Z" />,
  grafica: (
    <>
      <path d="M3.6 20.4h16.8" />
      <path d="M7.4 20.4v-6.2M12 20.4V6.4M16.6 20.4v-9" />
    </>
  ),
  puntero: <path d="M5.6 3.8 19 10.4l-6 1.8-1.8 6z" strokeLinejoin="round" />,
};

/**
 * Un icono. Decorativo por defecto —`aria-hidden`— porque siempre acompaña a
 * un texto que ya dice lo mismo; para el caso raro en que va solo, se le pasa
 * `title` y entonces sí se anuncia.
 */
export function Icon({
  name,
  title,
  ...rest
}: { name: IconName; title?: string } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
      {...rest}
    >
      {PATHS[name]}
    </svg>
  );
}

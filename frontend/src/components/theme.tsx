/**
 * Temas de la interfaz.
 *
 * El tema es una preferencia **del dispositivo**, no un dato del historial:
 * vive en `localStorage` junto al token y el temporizador, y no viaja a la
 * API. Así el PC puede ir en oscuro y el móvil en claro sin sincronizar nada
 * ni añadir un ajuste al backend.
 *
 * Aquí solo están el identificador y el nombre. **Los colores viven en el
 * CSS** (`[data-tema="..."]`): tenerlos también en TypeScript obligaría a
 * mantener dos copias de la misma paleta, y una de las dos acabaría mintiendo.
 * Las muestras del selector se pintan aplicando el propio `data-tema` al
 * cuadrito, que así hereda los colores reales del tema.
 */

import { useSyncExternalStore } from "react";

export type ThemeId = "carbon" | "indigo" | "bosque" | "sangre" | "oceano" | "violeta" | "claro";

export const THEMES: { id: ThemeId; name: string }[] = [
  { id: "carbon", name: "Carbón" },
  { id: "indigo", name: "Índigo" },
  { id: "bosque", name: "Bosque" },
  { id: "sangre", name: "Sangre" },
  { id: "oceano", name: "Océano" },
  { id: "violeta", name: "Violeta" },
  { id: "claro", name: "Claro" },
];

export const DEFAULT_THEME: ThemeId = "carbon";

/** Misma clave que el script antiparpadeo de `index.html`. */
const KEY = "fitup.tema";

const isTheme = (value: unknown): value is ThemeId => THEMES.some((t) => t.id === value);

export const themeName = (id: ThemeId): string =>
  THEMES.find((t) => t.id === id)?.name ?? id;

function read(): ThemeId {
  try {
    const saved = localStorage.getItem(KEY);
    return isTheme(saved) ? saved : DEFAULT_THEME;
  } catch {
    // Modo privado o almacenamiento bloqueado: el tema por defecto sirve.
    return DEFAULT_THEME;
  }
}

function apply(id: ThemeId) {
  document.documentElement.dataset.tema = id;
  // La barra del navegador y la de la PWA se pintan con el fondo del tema. Se
  // lee del CSS ya aplicado en vez de repetir el color aquí.
  const bg = getComputedStyle(document.documentElement).getPropertyValue("--bg").trim();
  const meta = document.querySelector('meta[name="theme-color"]');
  if (bg && meta) meta.setAttribute("content", bg);
}

/*
 * Store compartido, por el mismo motivo que el del temporizador: el evento
 * `storage` avisa a las **otras** pestañas, nunca a la que escribió. Sin él,
 * el selector de la caja lateral y el de la página de Ajustes tendrían cada
 * uno su copia y no se enterarían el uno del otro.
 */
let snapshot: ThemeId = read();
const listeners = new Set<() => void>();

// El script de `index.html` ya puso `data-tema` antes de pintar —para que no
// haya fogonazo del tema por defecto—, pero no la barra del navegador; y si
// ese script falló, esto deja el documento coherente igualmente.
if (typeof document !== "undefined") apply(snapshot);

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function publish(id: ThemeId) {
  snapshot = id;
  apply(id);
  for (const listener of listeners) listener();
  try {
    localStorage.setItem(KEY, id);
  } catch {
    // Sin persistencia el tema dura la sesión; no es motivo para fallar.
  }
}

if (typeof window !== "undefined") {
  window.addEventListener("storage", (e) => {
    if (e.key !== KEY || !isTheme(e.newValue)) return;
    snapshot = e.newValue;
    apply(snapshot);
    for (const listener of listeners) listener();
  });
}

/** Tema activo y cómo cambiarlo. */
export function useTheme() {
  const theme = useSyncExternalStore(
    subscribe,
    () => snapshot,
    () => DEFAULT_THEME,
  );
  return { theme, setTheme: publish };
}

/**
 * Selector de tema. Es un grupo de radios de verdad —no botones— para que las
 * flechas del teclado funcionen y el lector de pantalla anuncie cuál está
 * puesto. El nombre acompaña siempre a la muestra: un tema no se elige solo
 * por color.
 */
export function ThemePicker({ compact = false }: { compact?: boolean }) {
  const { theme, setTheme } = useTheme();

  return (
    <div className={compact ? "temas temas-compacto" : "temas"} role="radiogroup" aria-label="Tema">
      {THEMES.map((t) => (
        <label key={t.id} className="tema">
          <input
            type="radio"
            name={compact ? "tema-menu" : "tema-ajustes"}
            value={t.id}
            checked={t.id === theme}
            onChange={() => setTheme(t.id)}
          />
          <span className="tema-muestra" data-tema={t.id} aria-hidden="true" />
          <span className="tema-nombre">{t.name}</span>
        </label>
      ))}
    </div>
  );
}

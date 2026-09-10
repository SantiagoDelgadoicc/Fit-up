/**
 * Caja de ajustes al pie de la barra lateral.
 *
 * Es la puerta a lo que se toca de vez en cuando —el tema, el peso, la página
 * de Ajustes— y por eso no ocupa un hueco entre las pestañas de navegación:
 * compite con "Hoy" y "Calendario", que se usan a diario. En móvil no aparece
 * (ahí manda la barra inferior, donde Ajustes sigue siendo una pestaña).
 */

import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useBodyweight } from "../api/hooks";
import { Icon } from "./icons";
import { ThemePicker, themeName, useTheme } from "./theme";

export function SettingsBox() {
  const [open, setOpen] = useState(false);
  const { theme } = useTheme();
  const bodyweight = useBodyweight();
  const box = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setOpen(false);
      // Devolver el foco al botón: si no, Escape lo dejaba en el aire y el
      // siguiente tabulador empezaba desde el principio de la página.
      trigger.current?.focus();
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const peso = bodyweight.data ? `${bodyweight.data.weight_kg} kg` : "sin peso";

  return (
    <div className="ajustes-box" ref={box}>
      {open && (
        <div className="ajustes-menu" role="dialog" aria-label="Ajustes rápidos">
          <p className="ajustes-titulo">Tema</p>
          <ThemePicker compact />
          <hr className="ajustes-sep" />
          <div className="ajustes-dato">
            <span>Peso corporal</span>
            <strong>{peso}</strong>
          </div>
          <Link className="ajustes-item" to="/ajustes" onClick={() => setOpen(false)}>
            <Icon name="ajustes" />
            Ajustes
          </Link>
        </div>
      )}

      <button
        ref={trigger}
        type="button"
        className="ajustes-trigger"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="ajustes-marca" aria-hidden="true" />
        <span className="ajustes-txt">
          <strong>Ajustes</strong>
          <small>
            {themeName(theme)} · {peso}
          </small>
        </span>
        <span className="ajustes-chevron" aria-hidden="true">
          <Icon name="desplegar" />
        </span>
      </button>
    </div>
  );
}

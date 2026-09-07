/** Estructura de la app: navegación y rutas. */

import { NavLink, Route, Routes, useLocation } from "react-router-dom";

import { ToastProvider } from "./components/ui";
import CalendarPage from "./pages/Calendar";
import History from "./pages/History";
import RoutineEditor from "./pages/RoutineEditor";
import Routines from "./pages/Routines";
import Settings from "./pages/Settings";
import Today from "./pages/Today";
import Week from "./pages/Week";

/**
 * Cuerpo y Timer llegarán en sus fases; no se muestran deshabilitados porque
 * una pestaña que no hace nada es ruido, no una promesa.
 */
const TABS = [
  { to: "/", icon: "🏋️", label: "Hoy", end: true },
  { to: "/calendario", icon: "📅", label: "Calendario", end: false },
  { to: "/rutinas", icon: "📋", label: "Rutinas", end: false },
  { to: "/semana", icon: "🗓️", label: "Semana", end: false },
  { to: "/historial", icon: "📖", label: "Historial", end: false },
  { to: "/ajustes", icon: "⚙️", label: "Ajustes", end: false },
];

/** Páginas que aprovechan el ancho de una pantalla de PC. */
const WIDE = ["/calendario"];

export default function App() {
  const { pathname } = useLocation();
  const wide = WIDE.some((path) => pathname.startsWith(path));

  return (
    <ToastProvider>
      <div className="app">
        <nav className="nav" aria-label="Navegación principal">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">
              🏋️
            </span>
            Fit-Up
          </div>
          {TABS.map((tab) => (
            <NavLink key={tab.to} to={tab.to} end={tab.end}>
              <span className="nav-icon" aria-hidden="true">
                {tab.icon}
              </span>
              {tab.label}
            </NavLink>
          ))}
        </nav>

        <main className={wide ? "main wide" : "main"}>
          <Routes>
            <Route path="/" element={<Today />} />
            <Route path="/calendario" element={<CalendarPage />} />
            <Route path="/rutinas" element={<Routines />} />
            <Route path="/rutinas/:id" element={<RoutineEditor />} />
            <Route path="/semana" element={<Week />} />
            <Route path="/historial" element={<History />} />
            <Route path="/ajustes" element={<Settings />} />
            <Route path="*" element={<Today />} />
          </Routes>
        </main>
      </div>
    </ToastProvider>
  );
}

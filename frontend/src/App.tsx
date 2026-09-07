/** Estructura de la app: navegación y rutas. */

import { NavLink, Route, Routes } from "react-router-dom";

import { ToastProvider } from "./components/ui";
import History from "./pages/History";
import RoutineEditor from "./pages/RoutineEditor";
import Routines from "./pages/Routines";
import Settings from "./pages/Settings";
import Today from "./pages/Today";
import Week from "./pages/Week";

/**
 * Cinco destinos. Calendario, Cuerpo y Timer llegarán en sus fases; no se
 * muestran deshabilitados porque una pestaña que no hace nada es ruido, no
 * una promesa.
 */
const TABS = [
  { to: "/", icon: "🏋️", label: "Hoy", end: true },
  { to: "/rutinas", icon: "📋", label: "Rutinas", end: false },
  { to: "/semana", icon: "🗓️", label: "Semana", end: false },
  { to: "/historial", icon: "📖", label: "Historial", end: false },
  { to: "/ajustes", icon: "⚙️", label: "Ajustes", end: false },
];

export default function App() {
  return (
    <ToastProvider>
      <div className="app">
        <nav className="nav" aria-label="Navegación principal">
          {TABS.map((tab) => (
            <NavLink key={tab.to} to={tab.to} end={tab.end}>
              <span className="nav-icon" aria-hidden="true">
                {tab.icon}
              </span>
              {tab.label}
            </NavLink>
          ))}
        </nav>

        <main className="main">
          <Routes>
            <Route path="/" element={<Today />} />
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

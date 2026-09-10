/** Estructura de la app: navegación y rutas. */

import { Fragment } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";

import { Icon } from "./components/icons";
import type { IconName } from "./components/icons";
import { Mando } from "./components/mando";
import { SettingsBox } from "./components/SettingsBox";
import { TimerPill } from "./components/timer";
import { ToastProvider } from "./components/ui";
import Body from "./pages/Body";
import CalendarPage from "./pages/Calendar";
import History from "./pages/History";
import Progression from "./pages/Progression";
import RoutineEditor from "./pages/RoutineEditor";
import Routines from "./pages/Routines";
import Settings from "./pages/Settings";
import Timer from "./pages/Timer";
import Today from "./pages/Today";
import Week from "./pages/Week";

type Tab = { to: string; icon: IconName; label: string; end: boolean; soloMovil?: boolean };

/**
 * Las pestañas, en tres grupos.
 *
 * Ocho seguidas son una lista; agrupadas por lo que se hace con ellas —lo que
 * se registra, lo que se planifica, lo que se analiza— son un mapa. Los
 * títulos solo aparecen en la barra lateral: en la barra inferior del móvil no
 * hay sitio y las pestañas se leen seguidas, en este mismo orden.
 */
const GRUPOS: { titulo: string; tabs: Tab[] }[] = [
  {
    titulo: "Registro",
    tabs: [
      { to: "/", icon: "hoy", label: "Hoy", end: true },
      { to: "/calendario", icon: "calendario", label: "Calendario", end: false },
      { to: "/descanso", icon: "descanso", label: "Descanso", end: false },
    ],
  },
  {
    titulo: "Plan",
    tabs: [
      { to: "/rutinas", icon: "rutinas", label: "Rutinas", end: false },
      { to: "/semana", icon: "semana", label: "Semana", end: false },
    ],
  },
  {
    titulo: "Análisis",
    tabs: [
      { to: "/cuerpo", icon: "cuerpo", label: "Cuerpo", end: false },
      { to: "/historial", icon: "historial", label: "Historial", end: false },
      // En escritorio, Ajustes no es una pestaña: vive en la caja del pie
      // (`SettingsBox`). En móvil no hay caja, así que la pestaña se queda.
      { to: "/ajustes", icon: "ajustes", label: "Ajustes", end: false, soloMovil: true },
    ],
  },
];

/** Páginas que aprovechan el ancho de una pantalla de PC. */
const WIDE = ["/calendario", "/cuerpo", "/historial"];

export default function App() {
  const { pathname } = useLocation();
  // «Hoy» va aparte: es exacta, y `startsWith("/")` acertaría con todo.
  const wide = pathname === "/" || WIDE.some((path) => pathname.startsWith(path));

  return (
    <ToastProvider>
      <div className="app">
        <Mando />

        <div className="app-cuerpo">
          <nav className="nav" aria-label="Navegación principal">
            {/* La marca solo se pinta aquí en móvil, donde no hay barra de
                mando; en escritorio la oculta el CSS. */}
            <div className="brand">
              <span className="brand-mark" aria-hidden="true" />
              Fit-Up
            </div>

            {GRUPOS.map((grupo) => (
              <Fragment key={grupo.titulo}>
                <span className="nav-grupo" aria-hidden="true">
                  {grupo.titulo}
                </span>
                {grupo.tabs.map((tab) => (
                  <NavLink
                    key={tab.to}
                    to={tab.to}
                    end={tab.end}
                    className={tab.soloMovil ? "solo-movil" : undefined}
                  >
                    <span className="nav-icon" aria-hidden="true">
                      <Icon name={tab.icon} />
                    </span>
                    {tab.label}
                  </NavLink>
                ))}
              </Fragment>
            ))}

            <div className="spacer" />
            <TimerPill />
            <SettingsBox />
          </nav>

          <main className={wide ? "main wide" : "main"}>
            <Routes>
              <Route path="/" element={<Today />} />
              <Route path="/calendario" element={<CalendarPage />} />
              <Route path="/cuerpo" element={<Body />} />
              <Route path="/rutinas" element={<Routines />} />
              <Route path="/rutinas/:id" element={<RoutineEditor />} />
              <Route path="/rutinas/:id/progresion" element={<Progression />} />
              <Route path="/semana" element={<Week />} />
              <Route path="/historial" element={<History />} />
              <Route path="/descanso" element={<Timer />} />
              <Route path="/ajustes" element={<Settings />} />
              <Route path="*" element={<Today />} />
            </Routes>
          </main>
        </div>
      </div>
    </ToastProvider>
  );
}

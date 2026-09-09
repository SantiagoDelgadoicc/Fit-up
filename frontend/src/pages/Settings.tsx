/** Ajustes: apariencia, peso corporal, ventana de gracia, permisos y dispositivo. */

import { useEffect, useState } from "react";

import { api, getToken, localDate, setToken } from "../api/client";
import { useBodyweight, useSetBodyweight, useSetSetting, useSettings } from "../api/hooks";
import { ThemePicker } from "../components/theme";
import { ErrorCard, Loading, useToast } from "../components/ui";

export default function Settings() {
  const settings = useSettings();
  const bodyweight = useBodyweight();
  const saveWeight = useSetBodyweight();
  const saveSetting = useSetSetting();
  const toast = useToast();

  const [weight, setWeight] = useState("");
  const [grace, setGrace] = useState(3);
  const [token, setTokenInput] = useState(getToken() ?? "");

  useEffect(() => {
    if (bodyweight.data) setWeight(String(bodyweight.data.weight_kg));
  }, [bodyweight.data]);

  useEffect(() => {
    const value = settings.data?.["dias_gracia"];
    if (typeof value === "number") setGrace(value);
  }, [settings.data]);

  if (settings.isLoading) return <Loading rows={2} />;
  if (settings.error) return <ErrorCard error={settings.error} />;

  return (
    <div className="stack-lg">
      <header className="page-head">
        <h1>Ajustes</h1>
      </header>

      <section className="card stack">
        <h2>Apariencia</h2>
        <p className="faint" style={{ margin: 0 }}>
          El tema se guarda en este dispositivo, no en el historial: el PC puede ir en
          oscuro y el móvil en claro.
        </p>
        <ThemePicker />
      </section>

      <section className="card stack">
        <h2>Peso corporal</h2>
        <p className="faint" style={{ margin: 0 }}>
          Necesario para medir los ejercicios de peso corporal. Sin él, el sistema no
          puede calcular su carga y lo dirá en vez de suponerla.
        </p>
        <div className="row">
          <input
            className="num"
            type="number"
            min={1}
            step={0.1}
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
            aria-label="Peso en kilogramos"
          />
          <span className="muted">kg</span>
          <div className="spacer" />
          <button
            className="btn btn-sm btn-primary"
            disabled={!weight || saveWeight.isPending}
            onClick={() =>
              saveWeight.mutate(
                { date: localDate(), weight_kg: Number(weight) },
                {
                  onSuccess: () => toast("Peso guardado"),
                  onError: (e) => toast(e instanceof Error ? e.message : "Error", "error"),
                },
              )
            }
          >
            Guardar
          </button>
        </div>
      </section>

      <section className="card stack">
        <h2>Margen para registrar</h2>
        <p className="faint" style={{ margin: 0 }}>
          Días que un entrenamiento programado espera antes de contar como no realizado.
          Mientras tanto aparece como pendiente y no penaliza la adherencia.
        </p>
        <div className="row">
          <input
            className="num"
            type="number"
            min={0}
            max={30}
            value={grace}
            onChange={(e) => setGrace(Number(e.target.value))}
            aria-label="Días de margen"
          />
          <span className="muted">días</span>
          <div className="spacer" />
          <button
            className="btn btn-sm btn-primary"
            disabled={saveSetting.isPending}
            onClick={() =>
              saveSetting.mutate(
                { key: "dias_gracia", value: grace },
                {
                  onSuccess: () => toast("Margen actualizado"),
                  onError: (e) => toast(e instanceof Error ? e.message : "Error", "error"),
                },
              )
            }
          >
            Guardar
          </button>
        </div>
      </section>

      <section className="card stack">
        <h2>Acceso desde el móvil</h2>
        <p className="faint" style={{ margin: 0 }}>
          Al arrancar el servidor con <code>--lan</code> se muestra un token. Pégalo aquí
          para usar Fit-Up desde el móvil en la misma red WiFi.
        </p>
        <input
          type="password"
          value={token}
          onChange={(e) => setTokenInput(e.target.value)}
          placeholder="Token de acceso"
          aria-label="Token de acceso"
        />
        <div className="row">
          <button
            className="btn btn-sm btn-primary"
            onClick={() => {
              setToken(token.trim() || null);
              toast(token.trim() ? "Dispositivo emparejado" : "Token borrado");
            }}
          >
            Guardar token
          </button>
        </div>
      </section>

      <AgentScopes />

      <section className="card stack">
        <h2>Copia de seguridad</h2>
        <p className="faint" style={{ margin: 0 }}>
          Fit-Up hace una copia diaria automática al arrancar. También puedes descargar
          todos tus datos en JSON.
        </p>
        <div className="row">
          <button className="btn btn-sm" onClick={() => void downloadExport(toast)}>
            Descargar mis datos
          </button>
        </div>
      </section>
    </div>
  );
}

/** Los permisos del agente, con su nombre en cristiano y qué abre cada uno. */
const SCOPES: { key: string; label: string; hint: string }[] = [
  { key: "read", label: "Leer mis datos", hint: "Historial, rutinas, calendario y ranking." },
  { key: "propose", label: "Proponer cambios", hint: "Calcular sugerencias sin aplicarlas." },
  {
    key: "write_sessions",
    label: "Registrar entrenamientos",
    hint: "Anotar sesiones y marcar días como no realizados.",
  },
  {
    key: "write_routines",
    label: "Modificar rutinas y calendario",
    hint: "Crear versiones, aplicar progresiones y cambiar la semana.",
  },
  { key: "write_settings", label: "Cambiar ajustes", hint: "Peso corporal y preferencias." },
];

/**
 * Permisos del agente de IA.
 *
 * Importa cómo se presenta esto: **no es una frontera de seguridad**. El agente
 * corre en este mismo PC con control de la máquina y puede abrir la base de
 * datos por su cuenta (ADR-0004). Lo que estos interruptores evitan es la
 * equivocación —un modelo confundido escribiendo historial falso—, y decirlo
 * claro es parte del diseño: prometer protección que no existe sería peor que
 * no ofrecer nada.
 */
function AgentScopes() {
  const settings = useSettings();
  const save = useSetSetting();
  const toast = useToast();

  const stored = settings.data?.["agent_scopes"];
  const scopes = (typeof stored === "object" && stored !== null ? stored : {}) as Record<
    string,
    boolean
  >;
  // Sin ajuste guardado valen los del servidor: leer y proponer, escribir no.
  const valueOf = (key: string) =>
    key in scopes ? Boolean(scopes[key]) : key === "read" || key === "propose";

  const toggle = (key: string) => {
    const next = Object.fromEntries(SCOPES.map((s) => [s.key, valueOf(s.key)]));
    next[key] = !valueOf(key);
    save.mutate(
      { key: "agent_scopes", value: next },
      {
        onSuccess: () => toast(next[key] ? "Permiso concedido" : "Permiso retirado"),
        onError: (e) => toast(e instanceof Error ? e.message : "Error", "error"),
      },
    );
  };

  return (
    <section className="card stack">
      <h2>Permisos del agente</h2>
      <p className="faint" style={{ margin: 0 }}>
        Qué puede hacer un agente de IA que use la API declarándose como tal. Sirve para
        evitar equivocaciones suyas, <strong>no</strong> para contener a un programa
        hostil: cualquier proceso de este PC puede abrir la base de datos por su cuenta.
        Lo que de verdad protege tu historial es que todo queda registrado, versionado y
        con copia de seguridad.
      </p>
      {SCOPES.map((scope) => (
        <label key={scope.key} className="scope">
          <input
            type="checkbox"
            checked={valueOf(scope.key)}
            disabled={save.isPending}
            onChange={() => toggle(scope.key)}
          />
          <span>
            <strong>{scope.label}</strong>
            <span className="faint"> {scope.hint}</span>
          </span>
        </label>
      ))}
    </section>
  );
}

/**
 * Descarga el export como fichero.
 *
 * No sirve un `<a download>`: cuando la instancia exige token, el navegador no
 * envia la cabecera `Authorization` en una navegacion normal y la descarga
 * fallaria con 401 sin explicacion.
 */
async function downloadExport(toast: (text: string, kind?: "ok" | "error") => void) {
  try {
    const data = await api<unknown>("/export");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `fitup-${localDate()}.json`;
    link.click();
    URL.revokeObjectURL(url);
    toast("Datos descargados");
  } catch (e) {
    toast(e instanceof Error ? e.message : "No se pudo descargar", "error");
  }
}

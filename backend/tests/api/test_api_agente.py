"""La superficie que consume el agente externo: actor, permisos y traza.

Lo que se prueba aquí no es que el agente sea inofensivo —no puede serlo, tiene
control del PC (ADR-0004)— sino que **deja huella y opera dentro de unos
límites mientras use la API**, que es el contrato que Fit-Up sí puede ofrecer.
"""

from __future__ import annotations

from fitup.api.agent import ACTOR_HEADER, DEFAULT_SCOPES, SCOPES_KEY
from helpers_api import SUNDAY, make_routine

AGENTE = {ACTOR_HEADER: "agente"}


def _permitir(client, *scopes: str) -> None:
    """Activa permisos del agente como lo haría el usuario desde Ajustes."""
    valores = dict(DEFAULT_SCOPES) | {scope: True for scope in scopes}
    response = client.put(f"/api/ajustes/{SCOPES_KEY}", json={"value": valores})
    assert response.status_code == 200, response.text


def _sesion(day=SUNDAY) -> dict:
    return {
        "date": day.isoformat(),
        "exercises": [
            {"exercise_slug": "press_banca", "sets": [{"set_no": 1, "reps": 8, "weight_kg": 40.0}]}
        ],
    }


# --------------------------------------------------------------------- Actor


def test_sin_cabecera_el_actor_es_el_usuario(client):
    """El comportamiento de siempre no cambia: la interfaz no manda cabecera."""
    assert client.post("/api/sesiones", json=_sesion()).status_code == 201

    entradas = client.get("/api/auditoria").json()
    assert [e["actor"] for e in entradas if e["action"] == "log_session"] == ["usuario"]


def test_un_actor_desconocido_se_rechaza_en_vez_de_pasar_por_usuario(client):
    """Degradar a `usuario` dejaría al agente escribiendo de incógnito.

    Es el fallo que haría inútil toda la traza, así que la cabecera mal escrita
    tiene que doler.
    """
    response = client.post("/api/sesiones", json=_sesion(), headers={ACTOR_HEADER: "superusuario"})
    # 422 como cualquier otra entrada que el dominio rechaza, no un 400 aparte.
    assert response.status_code == 422
    assert "superusuario" in response.json()["detail"]


def test_la_escritura_del_agente_queda_registrada_como_suya(client):
    _permitir(client, "write_sessions")
    assert client.post("/api/sesiones", json=_sesion(), headers=AGENTE).status_code == 201

    entradas = client.get("/api/auditoria", params={"actor": "agente"}).json()
    acciones = [e["action"] for e in entradas]
    assert "log_session" in acciones
    assert all(e["actor"] == "agente" for e in entradas)


# -------------------------------------------------------------------- Scopes


def test_por_defecto_el_agente_no_escribe(client):
    """ADR-0004 §3: `read` y `propose` sí, escrituras desactivadas."""
    assert client.post("/api/sesiones", json=_sesion(), headers=AGENTE).status_code == 403
    assert (
        client.post("/api/rutinas", json={"name": "X", "exercises": []}, headers=AGENTE).status_code
        == 403
    )


def test_por_defecto_el_agente_si_lee(client):
    """El guardarraíl frena escrituras, no consultas."""
    assert client.get("/api/ranking", headers=AGENTE).status_code == 200
    assert client.get("/api/rutinas", headers=AGENTE).status_code == 200


def test_el_usuario_no_pasa_por_los_permisos_del_agente(client):
    """Los scopes son para el agente. El usuario es el dueño de sus datos."""
    assert client.post("/api/sesiones", json=_sesion()).status_code == 201


def test_los_permisos_son_por_familia(client):
    """Activar sesiones no debe abrir de paso las rutinas."""
    _permitir(client, "write_sessions")
    assert client.post("/api/sesiones", json=_sesion(), headers=AGENTE).status_code == 201
    assert (
        client.post("/api/rutinas", json={"name": "X", "exercises": []}, headers=AGENTE).status_code
        == 403
    )


def test_un_rechazo_deja_rastro(client):
    """Un intento bloqueado dice más que uno permitido: tiene que verse."""
    client.post("/api/sesiones", json=_sesion(), headers=AGENTE)

    rechazos = client.get("/api/auditoria", params={"result": "rechazado"}).json()
    assert [e["action"] for e in rechazos] == ["scope:write_sessions"]
    assert rechazos[0]["actor"] == "agente"


def test_los_permisos_se_pueden_consultar(client):
    """Para que el agente sepa qué no va a poder hacer antes de intentarlo."""
    assert client.get("/api/agente/permisos", headers=AGENTE).json() == DEFAULT_SCOPES


# ------------------------------------------------------------------- Backups


def test_el_primer_cambio_del_agente_guarda_una_copia(client, tmp_path):
    """ADR-0004 §2: la reversibilidad es la protección real, no el permiso."""
    _permitir(client, "write_sessions")
    client.post("/api/sesiones", json=_sesion(), headers=AGENTE)

    copias = list((tmp_path / "backups").glob("fitup-agente-*.db"))
    assert len(copias) == 1


def test_las_escrituras_seguidas_no_hacen_una_copia_cada_una(client, tmp_path):
    """Una copia por escritura llenaría el disco durante una ráfaga."""
    _permitir(client, "write_sessions")
    for day in ("2026-03-11", "2026-03-12", "2026-03-13"):
        client.post("/api/sesiones", json=_sesion() | {"date": day}, headers=AGENTE)

    assert len(list((tmp_path / "backups").glob("fitup-agente-*.db"))) == 1


def test_el_usuario_no_dispara_copias_de_lote(client, tmp_path):
    """La copia previa existe por el agente; el usuario ya tiene la diaria."""
    client.post("/api/sesiones", json=_sesion())
    assert list((tmp_path / "backups").glob("fitup-agente-*.db")) == []


# ---------------------------------------------------------------- Auditoría


def test_la_auditoria_cubre_tambien_rutinas_y_planificacion(client):
    """Antes solo se auditaban sesiones y progresiones: quedaba medio ciego."""
    routine_id = make_routine(client)
    client.put("/api/semana", json={"days": {"0": routine_id}, "effective_from": "2026-03-01"})
    client.put(
        "/api/excepciones/2026-03-16", json={"reason": "viaje", "routine_id": None, "note": None}
    )
    client.put("/api/peso", json={"date": "2026-03-15", "weight_kg": 78.0})

    acciones = {e["action"] for e in client.get("/api/auditoria", params={"limit": 100}).json()}
    assert {"create_routine", "set_week", "set_exception", "set_bodyweight"} <= acciones


def test_la_auditoria_se_lee_de_lo_mas_reciente_hacia_atras(client):
    make_routine(client, name="Primera")
    make_routine(client, name="Segunda")

    entradas = client.get("/api/auditoria", params={"limit": 2}).json()
    assert [e["payload"]["name"] for e in entradas] == ["Segunda", "Primera"]


def test_read_es_el_interruptor_general(client):
    """Apagar la lectura tiene que dejar al agente fuera de todo.

    Si `read` solo cubriera los endpoints que alguien recordó marcar, sería una
    promesa a medias: el interruptor va en el router entero.
    """
    _permitir(client)  # deja `read` en su valor por defecto (activado)
    assert client.get("/api/ranking", headers=AGENTE).status_code == 200

    valores = dict(DEFAULT_SCOPES) | {"read": False}
    client.put(f"/api/ajustes/{SCOPES_KEY}", json={"value": valores})

    assert client.get("/api/ranking", headers=AGENTE).status_code == 403
    assert client.get("/api/rutinas", headers=AGENTE).status_code == 403
    # El usuario sigue entrando: los permisos son del agente.
    assert client.get("/api/ranking").status_code == 200


def test_las_propuestas_tienen_su_propio_permiso(client):
    """Proponer no es escribir, pero tampoco es mirar: se apaga por separado."""
    routine_id = make_routine(client)
    assert client.get(f"/api/rutinas/{routine_id}/progresion", headers=AGENTE).status_code == 200

    valores = dict(DEFAULT_SCOPES) | {"propose": False}
    client.put(f"/api/ajustes/{SCOPES_KEY}", json={"value": valores})

    assert client.get(f"/api/rutinas/{routine_id}/progresion", headers=AGENTE).status_code == 403
    # Consultar la rutina sigue estando permitido: eso es `read`.
    assert client.get(f"/api/rutinas/{routine_id}", headers=AGENTE).status_code == 200

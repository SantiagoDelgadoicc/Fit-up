"""Contrato HTTP de F1.

Prueban el adaptador: traducción de entrada, mapeo de errores de dominio a
códigos de estado y forma de la respuesta. La lógica ya está probada en la
capa de aplicación; aquí no se repite.
"""

from __future__ import annotations

from helpers_api import FRIDAY, MONDAY, SUNDAY, TUESDAY, WEDNESDAY, make_routine, schedule

# --------------------------------------------------------------------------
# Catálogo
# --------------------------------------------------------------------------


def test_el_catalogo_esta_sembrado_al_arrancar(client):
    assert len(client.get("/api/catalogo/musculos").json()) >= 15
    assert len(client.get("/api/catalogo/ejercicios").json()) >= 50
    assert len(client.get("/api/catalogo/reglas").json()) >= 8


def test_un_ejercicio_trae_sus_musculos_y_su_regla(client):
    body = client.get("/api/catalogo/ejercicios/flexiones").json()
    assert body["load_type"] == "corporal"
    assert body["load_factor"] > 0
    assert body["next_variant_slug"] == "flexiones_declinadas"
    assert {m["muscle_slug"] for m in body["muscles"]} >= {"pectoral", "triceps"}


def test_un_ejercicio_inexistente_da_404(client):
    assert client.get("/api/catalogo/ejercicios/fantasma").status_code == 404


# --------------------------------------------------------------------------
# Rutinas
# --------------------------------------------------------------------------


def test_crear_una_rutina_con_prescripcion_compacta(client):
    routine_id = make_routine(client)
    body = client.get(f"/api/rutinas/{routine_id}").json()
    assert body["version_no"] == 1
    assert len(body["exercises"][0]["sets"]) == 3
    assert body["exercises"][0]["sets"][0]["target_reps"] == 15


def test_una_rutina_sin_ejercicios_da_422(client):
    response = client.post("/api/rutinas", json={"name": "Vacía", "exercises": []})
    assert response.status_code == 422


def test_un_ejercicio_sin_series_ni_spec_da_422(client):
    response = client.post(
        "/api/rutinas",
        json={"name": "X", "exercises": [{"exercise_slug": "flexiones"}]},
    )
    assert response.status_code == 422
    assert "series" in response.json()["detail"]


def test_un_ejercicio_inexistente_en_una_rutina_da_404(client):
    response = client.post(
        "/api/rutinas",
        json={
            "name": "X",
            "exercises": [{"exercise_slug": "fantasma", "spec": {"count": 3, "reps": 10}}],
        },
    )
    assert response.status_code == 404


def test_editar_una_rutina_crea_una_version_y_conserva_la_anterior(client):
    routine_id = make_routine(client)
    updated = client.put(
        f"/api/rutinas/{routine_id}",
        json={"exercises": [{"exercise_slug": "flexiones", "spec": {"count": 3, "reps": 16}}]},
    ).json()
    assert updated["version_no"] == 2

    v1 = client.get(f"/api/rutinas/{routine_id}?version=1").json()
    assert len(v1["exercises"]) == 2
    assert v1["exercises"][0]["sets"][0]["target_reps"] == 15


def test_archivar_una_rutina_la_saca_del_listado(client):
    routine_id = make_routine(client)
    assert client.delete(f"/api/rutinas/{routine_id}").status_code == 204
    assert client.get("/api/rutinas").json() == []
    assert len(client.get("/api/rutinas?include_archived=true").json()) == 1


def test_una_rutina_inexistente_da_404(client):
    assert client.get("/api/rutinas/999").status_code == 404


# --------------------------------------------------------------------------
# Semana
# --------------------------------------------------------------------------


def test_organizar_y_consultar_la_semana(client):
    routine_id = make_routine(client)
    schedule(client, routine_id)
    week = client.get("/api/semana").json()
    assert week["days"]["0"] == routine_id
    assert week["days"]["1"] is None
    assert week["names"]["4"] == "Empuje"


def test_programar_una_rutina_inexistente_da_404(client):
    response = client.put("/api/semana", json={"days": {"0": 999}, "effective_from": "2026-03-01"})
    assert response.status_code == 404


# --------------------------------------------------------------------------
# El día
# --------------------------------------------------------------------------


def test_hoy_devuelve_el_estado_del_dia(client):
    routine_id = make_routine(client)
    schedule(client, routine_id)
    body = client.get("/api/hoy").json()
    assert body["date"] == SUNDAY.isoformat()
    assert body["state"] == "rest"  # el domingo no está programado


def test_un_dia_programado_trae_el_plan_y_permite_registrar(client):
    routine_id = make_routine(client)
    schedule(client, routine_id)
    body = client.get(f"/api/dias/{FRIDAY}").json()

    assert body["state"] == "pending"
    assert body["can_log"] is True
    assert len(body["planned"]["exercises"]) == 2


def test_consultar_un_dia_futuro_da_422(client):
    assert client.get("/api/dias/2027-01-01").status_code == 422


# --------------------------------------------------------------------------
# Registro
# --------------------------------------------------------------------------


def test_hice_esta_rutina_registra_el_plan_completo(client):
    routine_id = make_routine(client)
    schedule(client, routine_id)
    response = client.post("/api/sesiones/como-planificado", json={"date": FRIDAY.isoformat()})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["is_retroactive"] is True
    assert len(body["exercises"]) == 2
    assert [s["reps"] for s in body["exercises"][0]["sets"]] == [15, 15, 15]


def test_registrar_un_dia_sin_rutina_como_planificado_da_422(client):
    routine_id = make_routine(client)
    schedule(client, routine_id)
    response = client.post("/api/sesiones/como-planificado", json={"date": TUESDAY.isoformat()})
    assert response.status_code == 422


def test_registrar_dos_veces_el_mismo_dia_da_409(client):
    routine_id = make_routine(client)
    schedule(client, routine_id)
    client.post("/api/sesiones/como-planificado", json={"date": FRIDAY.isoformat()})
    response = client.post("/api/sesiones/como-planificado", json={"date": FRIDAY.isoformat()})
    assert response.status_code == 409


def test_registrar_en_el_futuro_da_422(client):
    routine_id = make_routine(client)
    schedule(client, routine_id)
    response = client.post("/api/sesiones/como-planificado", json={"date": "2027-01-01"})
    assert response.status_code == 422
    assert "futuro" in response.json()["detail"]


def test_la_cabecera_de_idempotencia_no_duplica(client):
    """Un cliente móvil con mala cobertura reintenta; no debe crear dos sesiones."""
    routine_id = make_routine(client)
    schedule(client, routine_id)
    headers = {"Idempotency-Key": "abc-123"}
    first = client.post(
        "/api/sesiones/como-planificado", json={"date": FRIDAY.isoformat()}, headers=headers
    )
    second = client.post(
        "/api/sesiones/como-planificado", json={"date": FRIDAY.isoformat()}, headers=headers
    )

    assert first.json()["id"] == second.json()["id"]
    assert len(client.get("/api/sesiones").json()) == 1


def test_registro_libre_con_rir(client):
    response = client.post(
        "/api/sesiones",
        json={
            "date": TUESDAY.isoformat(),
            "exercises": [
                {
                    "exercise_slug": "press_banca",
                    "sets": [{"set_no": 1, "reps": 8, "weight_kg": 42.5, "rir": 2}],
                }
            ],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["origin"] == "adhoc"
    assert body["exercises"][0]["sets"][0]["rir"] == 2


def test_registrar_una_sesion_parcial(client):
    routine_id = make_routine(client)
    schedule(client, routine_id)
    response = client.post(
        "/api/sesiones/como-planificado",
        json={"date": FRIDAY.isoformat(), "status": "partial"},
    )
    assert response.json()["status"] == "partial"
    assert client.get(f"/api/dias/{FRIDAY}").json()["state"] == "partial"


def test_declarar_que_no_se_entreno(client):
    routine_id = make_routine(client)
    schedule(client, routine_id)
    response = client.post("/api/sesiones/no-realizado", json={"date": MONDAY.isoformat()})
    assert response.status_code == 201
    assert client.get(f"/api/dias/{MONDAY}").json()["state"] == "missed"


def test_borrar_una_sesion(client):
    routine_id = make_routine(client)
    schedule(client, routine_id)
    session_id = client.post(
        "/api/sesiones/como-planificado", json={"date": FRIDAY.isoformat()}
    ).json()["id"]

    assert client.delete(f"/api/sesiones/{session_id}").status_code == 204
    assert client.get(f"/api/sesiones/{session_id}").status_code == 404


# --------------------------------------------------------------------------
# Pendientes y calendario
# --------------------------------------------------------------------------


def test_los_pendientes_listan_lo_que_falta_por_registrar(client):
    routine_id = make_routine(client)
    schedule(client, routine_id)
    pendientes = client.get("/api/pendientes").json()

    assert [p["date"] for p in pendientes] == [FRIDAY.isoformat()]
    assert pendientes[0]["routine_name"] == "Empuje"


def test_registrar_vacia_los_pendientes(client):
    routine_id = make_routine(client)
    schedule(client, routine_id)
    client.post("/api/sesiones/como-planificado", json={"date": FRIDAY.isoformat()})
    assert client.get("/api/pendientes").json() == []


def test_el_calendario_del_mes_trae_los_estados_y_la_adherencia(client):
    routine_id = make_routine(client)
    schedule(client, routine_id)
    client.post("/api/sesiones/como-planificado", json={"date": MONDAY.isoformat()})

    body = client.get("/api/calendario/2026/3").json()
    estados = {d["date"]: d["state"] for d in body["days"]}

    assert body["end"] == SUNDAY.isoformat()  # nunca pasa de hoy
    assert estados[MONDAY.isoformat()] == "done"
    assert estados[TUESDAY.isoformat()] == "rest"
    assert estados[WEDNESDAY.isoformat()] == "missed"
    assert estados[FRIDAY.isoformat()] == "pending"
    assert body["adherence"] is not None


def test_la_adherencia_es_nula_cuando_nada_computa(client):
    """Un 0 % sobre datos inexistentes sería una afirmación falsa."""
    assert client.get("/api/calendario/2026/3").json()["adherence"] is None


def test_una_excepcion_excusa_el_dia(client):
    routine_id = make_routine(client)
    schedule(client, routine_id)
    assert client.put(f"/api/excepciones/{WEDNESDAY}", json={"reason": "lesion"}).status_code == 204

    assert client.get(f"/api/dias/{WEDNESDAY}").json()["state"] == "excused"
    client.delete(f"/api/excepciones/{WEDNESDAY}")
    assert client.get(f"/api/dias/{WEDNESDAY}").json()["state"] == "missed"


# --------------------------------------------------------------------------
# Sistema
# --------------------------------------------------------------------------


def test_salud(client):
    body = client.get("/api/salud").json()
    assert body["ok"] is True
    assert body["schema_version"] >= 1


def test_peso_corporal(client):
    assert client.get("/api/peso/actual").json() is None
    client.put("/api/peso", json={"date": MONDAY.isoformat(), "weight_kg": 75.5})
    assert client.get("/api/peso/actual").json()["weight_kg"] == 75.5
    assert len(client.get("/api/peso").json()) == 1


def test_ajustes(client):
    assert client.get("/api/ajustes").json()["dias_gracia"] == 3
    client.put("/api/ajustes/dias_gracia", json={"value": 7})
    assert client.get("/api/ajustes").json()["dias_gracia"] == 7


def test_la_ventana_de_gracia_configurada_cambia_los_pendientes(client):
    routine_id = make_routine(client)
    schedule(client, routine_id)
    client.put("/api/ajustes/dias_gracia", json={"value": 10})
    assert MONDAY.isoformat() in [p["date"] for p in client.get("/api/pendientes").json()]


def test_export_completo(client):
    routine_id = make_routine(client)
    schedule(client, routine_id)
    client.post("/api/sesiones/como-planificado", json={"date": FRIDAY.isoformat()})

    body = client.get("/api/export").json()
    assert body["format_version"] == "1"
    assert body["catalog"]["exercises"] and body["routines"] and body["sessions"]
    assert "instruccion" in body["note"]


def test_backup(client, tmp_path):
    response = client.post("/api/backup")
    assert response.status_code == 201
    assert "fitup-" in response.json()["path"]


# --------------------------------------------------------------------------
# Autenticación
# --------------------------------------------------------------------------


def test_sin_token_la_api_protegida_responde_401(secured):
    assert secured.get("/api/catalogo/musculos").status_code == 401


def test_un_token_incorrecto_responde_401(secured):
    response = secured.get("/api/catalogo/musculos", headers={"Authorization": "Bearer otro"})
    assert response.status_code == 401


def test_el_token_correcto_da_acceso(secured):
    response = secured.get("/api/catalogo/musculos", headers={"Authorization": "Bearer secreto"})
    assert response.status_code == 200


def test_el_openapi_se_genera(client):
    """De aquí salen los tipos del frontend y la documentación del agente."""
    spec = client.get("/openapi.json").json()
    assert "/api/sesiones/como-planificado" in spec["paths"]
    assert spec["info"]["title"] == "Fit-Up"

"""Contrato HTTP de la progresión.

Los casos de uso ya están probados en `tests/application/test_progresion.py`.
Aquí se comprueba lo propio del adaptador: rutas, códigos de estado y que un
rechazo del dominio llegue como 409 con su motivo, no como un 500.
"""

from __future__ import annotations

import pytest

from helpers_api import MONDAY, WEDNESDAY, make_routine, schedule


@pytest.fixture
def routine(client) -> int:
    routine_id = make_routine(client)
    schedule(client, routine_id)
    return routine_id


def entrenar(client, *days) -> None:
    for day in days:
        response = client.post("/api/sesiones/como-planificado", json={"date": day.isoformat()})
        assert response.status_code == 201, response.text


def test_evaluar_devuelve_un_veredicto_con_motivo_por_ejercicio(client, routine):
    body = client.get(f"/api/rutinas/{routine}/progresion").json()

    assert body["routine_id"] == routine
    assert body["ready"] == 0
    assert {i["exercise_slug"] for i in body["items"]} == {"flexiones", "press_banca"}
    assert all(i["reason"] for i in body["items"])
    assert all(i["applicable"] is False for i in body["items"])


def test_la_regla_heredada_del_catalogo_se_declara_como_tal(client, routine):
    body = client.get(f"/api/rutinas/{routine}/progresion").json()
    flexiones = next(i for i in body["items"] if i["exercise_slug"] == "flexiones")

    assert flexiones["rule_slug"] == "reps_hasta_150"
    assert flexiones["rule_inherited"] is True


def test_aplicar_devuelve_la_version_nueva_y_los_eventos(client, routine):
    entrenar(client, MONDAY, WEDNESDAY)

    response = client.post(f"/api/rutinas/{routine}/progresion", json={"exercises": ["flexiones"]})

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["routine"]["version_no"] == 2
    assert len(body["events"]) == 1
    assert body["events"][0]["before_summary"] == "3x15"
    assert body["events"][0]["after_summary"] == "3x17"


def test_aplicar_lo_que_no_puede_progresar_es_conflicto_con_motivo(client, routine):
    entrenar(client, MONDAY)  # una sesión no basta

    response = client.post(f"/api/rutinas/{routine}/progresion", json={"exercises": ["flexiones"]})

    assert response.status_code == 409
    assert "no puede progresar" in response.json()["detail"]


def test_aplicar_sin_ejercicios_es_rechazado_por_el_contrato(client, routine):
    response = client.post(f"/api/rutinas/{routine}/progresion", json={"exercises": []})
    assert response.status_code == 422


def test_el_aviso_de_hoy_lista_las_rutinas_con_algo_que_ofrecer(client, routine):
    assert client.get("/api/progresion/listas").json() == []

    entrenar(client, MONDAY, WEDNESDAY)
    listas = client.get("/api/progresion/listas").json()

    assert listas[0]["routine_id"] == routine
    assert listas[0]["ready"] == 2


def test_deshacer_revierte_y_no_se_repite(client, routine):
    entrenar(client, MONDAY, WEDNESDAY)
    aplicado = client.post(
        f"/api/rutinas/{routine}/progresion", json={"exercises": ["flexiones"]}
    ).json()
    event_id = aplicado["events"][0]["id"]

    response = client.post(f"/api/progresiones/{event_id}/deshacer")
    assert response.status_code == 201, response.text
    assert response.json()["routine"]["version_no"] == 3

    repetido = client.post(f"/api/progresiones/{event_id}/deshacer")
    assert repetido.status_code == 409


def test_el_historial_de_progresiones_conserva_la_reversion(client, routine):
    entrenar(client, MONDAY, WEDNESDAY)
    aplicado = client.post(
        f"/api/rutinas/{routine}/progresion", json={"exercises": ["flexiones"]}
    ).json()
    client.post(f"/api/progresiones/{aplicado['events'][0]['id']}/deshacer")

    eventos = client.get(f"/api/progresiones?routine_id={routine}").json()

    assert len(eventos) == 2
    assert any(e["is_reversal"] for e in eventos)
    assert any(e["reverted"] for e in eventos)


def test_deshacer_una_progresion_inexistente_es_404(client):
    assert client.post("/api/progresiones/999/deshacer").status_code == 404


def test_guardar_una_rutina_conserva_la_regla_elegida(client):
    """Blinda el contrato del que depende el selector de regla del editor.

    El fallo que motivó este test era de interfaz —el editor no enviaba
    `rule_slug` y cada guardado lo borraba— y se corrigió y verificó en la app
    real. Lo que se fija aquí es el otro extremo: que enviarlo baste para que
    persista y el motor lo use en vez de heredar el del catálogo.
    """
    routine_id = make_routine(client)
    actual = client.get(f"/api/rutinas/{routine_id}").json()

    respuesta = client.put(
        f"/api/rutinas/{routine_id}",
        json={
            "exercises": [
                {
                    "exercise_slug": e["exercise_slug"],
                    "rule_slug": "manual" if e["exercise_slug"] == "flexiones" else None,
                    "sets": e["sets"],
                }
                for e in actual["exercises"]
            ]
        },
    )
    assert respuesta.status_code == 200, respuesta.text

    guardada = client.get(f"/api/rutinas/{routine_id}").json()
    flexiones = next(e for e in guardada["exercises"] if e["exercise_slug"] == "flexiones")
    assert flexiones["rule_slug"] == "manual"

    evaluacion = client.get(f"/api/rutinas/{routine_id}/progresion").json()
    item = next(i for i in evaluacion["items"] if i["exercise_slug"] == "flexiones")
    assert item["rule_slug"] == "manual"
    assert item["rule_inherited"] is False

"""Contrato HTTP del ranking muscular.

Lo que importa aquí, más que los códigos de estado, es que el contrato no
permita mentir: un músculo sin rango tiene que llegar al cliente como `null`
y no como cero, y la respuesta tiene que declarar que la calibración es
provisional.
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


def pesar(client, kg=75.0) -> None:
    response = client.put("/api/peso", json={"date": "2026-01-01", "weight_kg": kg})
    assert response.status_code == 200, response.text


def muscle(body, slug):
    return next(e for e in body["entries"] if e["muscle_slug"] == slug)


def test_el_ranking_devuelve_los_dieciocho_musculos_con_o_sin_datos(client):
    body = client.get("/api/ranking").json()

    assert len(body["entries"]) == 18
    assert body["provisional"] is True
    assert body["formula_version"] == "v2"


def test_un_musculo_sin_rango_llega_como_null_y_no_como_cero(client):
    """Pintar un cero convertiría "sin medir" en "el más débil de todos"."""
    body = client.get("/api/ranking").json()
    gemelos = muscle(body, "gemelos")

    assert gemelos["tier"] == "sin_datos"
    assert gemelos["development"] is None
    assert gemelos["has_data"] is False


def test_sin_peso_corporal_la_respuesta_explica_que_falta(client, routine):
    entrenar(client, MONDAY, WEDNESDAY)
    body = client.get("/api/ranking").json()

    assert body["bodyweight_kg"] is None
    # v2 mide repeticiones, no kilos: el rango sale igual sin peso corporal.
    assert body["measured"] > 0
    assert any("peso corporal" in n for n in body["notes"])


def test_con_peso_y_entrenamiento_aparece_el_rango(client, routine):
    pesar(client)
    entrenar(client, MONDAY, WEDNESDAY)
    body = client.get("/api/ranking").json()

    pectoral = muscle(body, "pectoral")
    assert pectoral["has_data"] is True
    assert pectoral["development"] > 0
    assert pectoral["tier"] != "sin_datos"
    assert pectoral["days_since_stimulus"] is not None


def test_el_ranking_incluye_los_avisos_de_equilibrio(client, routine):
    pesar(client)
    entrenar(client, MONDAY, WEDNESDAY)
    body = client.get("/api/ranking").json()

    assert {c["key"] for c in body["balance"]} == {"empuje_tiron", "cuadriceps_femoral"}
    assert all(c["message"] for c in body["balance"])


def test_la_ficha_de_un_musculo_explica_de_donde_sale_el_rango(client, routine):
    pesar(client)
    entrenar(client, MONDAY, WEDNESDAY)
    body = client.get("/api/ranking/pectoral").json()

    assert body["muscle"]["muscle_slug"] == "pectoral"
    assert body["factors"]["marca_confirmada"] > 0
    assert body["muscle"]["leading_exercise"]
    assert body["muscle"]["next_mark"]
    assert body["points_to_next_tier"] is not None
    assert [e["exercise_slug"] for e in body["exercises"]]
    assert body["recent"]["sessions"] == 2


def test_la_ficha_de_un_musculo_inexistente_es_404(client):
    assert client.get("/api/ranking/musculo_inventado").status_code == 404


def test_el_snapshot_se_puede_forzar_y_alimenta_el_historico(client, routine):
    pesar(client)
    entrenar(client, MONDAY, WEDNESDAY)

    response = client.post("/api/ranking/snapshot")
    assert response.status_code == 201
    assert response.json()["muscles"] == 18

    historico = client.get("/api/ranking/pectoral").json()["history"]
    assert len(historico) == 1
    assert historico[0]["tier"]


def test_la_evolucion_de_un_ejercicio_devuelve_un_punto_por_sesion(client, routine):
    pesar(client)
    entrenar(client, MONDAY, WEDNESDAY)
    body = client.get("/api/metricas/ejercicios/press_banca").json()

    assert len(body["points"]) == 2
    assert body["best_e1rm_kg"] > 0
    assert all(p["volume_kg"] > 0 for p in body["points"])


def test_la_evolucion_de_un_ejercicio_inexistente_es_404(client):
    assert client.get("/api/metricas/ejercicios/inventado").status_code == 404

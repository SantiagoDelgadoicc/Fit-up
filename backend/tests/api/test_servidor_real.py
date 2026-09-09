"""Prueba de humo contra un servidor uvicorn real.

Existe por un fallo concreto: la API rompía con
``SQLite objects created in a thread can only be used in that same thread``
y los 42 tests con ``TestClient`` pasaban igualmente. FastAPI resuelve la
dependencia y ejecuta el endpoint en hilos distintos de su threadpool, y bajo
``TestClient`` ese reparto no se reprodujo.

La lección: los dobles pueden ocultar precisamente lo que hay que verificar.

Y una segunda, aprendida al escribir este fichero: la primera versión hacía
peticiones **en serie** y pasaba igual con el fallo puesto, porque el
threadpool reutilizaba el mismo hilo. Solo lanzándolas **en paralelo** —como
hace la interfaz al cargar una pantalla— se reparten entre varios hilos y el
error aparece. Un test que no falla ante el fallo que dice cubrir no sirve.
"""

from __future__ import annotations

import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import httpx
import pytest
import uvicorn

from fitup.api.app import create_app
from fitup.api.deps import Settings


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    db = tmp_path_factory.mktemp("real") / "fitup.db"
    app = create_app(Settings(db_path=db, token=None, require_token=False))
    port = _free_port()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    running = uvicorn.Server(config)
    thread = threading.Thread(target=running.run, daemon=True)
    thread.start()

    deadline = time.time() + 20
    while not running.started and time.time() < deadline:
        time.sleep(0.05)
    if not running.started:  # pragma: no cover - solo si el arranque falla
        pytest.fail("el servidor no arrancó")

    yield f"http://127.0.0.1:{port}"

    running.should_exit = True
    thread.join(timeout=10)


def test_peticiones_en_paralelo_no_rompen_la_conexion(server):
    """Reproduce lo que hace la interfaz al abrir una pantalla.

    Varias peticiones a la vez obligan al threadpool de FastAPI a usar hilos
    distintos, que es exactamente la condición que hacía fallar a SQLite.
    """
    rutas = [
        "/api/salud",
        "/api/catalogo/ejercicios",
        "/api/catalogo/musculos",
        "/api/catalogo/reglas",
        "/api/rutinas",
        "/api/semana",
        "/api/hoy",
        "/api/pendientes",
        "/api/sesiones",
        "/api/ajustes",
        "/api/peso/actual",
    ]
    with ThreadPoolExecutor(max_workers=len(rutas)) as pool:
        respuestas = list(pool.map(lambda r: httpx.get(f"{server}{r}", timeout=20), rutas * 3))

    fallos = [
        (r.request.url.path, r.status_code, r.text[:160])
        for r in respuestas
        if r.status_code != 200
    ]
    assert fallos == []


def test_un_recorrido_completo_sobre_el_servidor_real(server):
    """Varios endpoints seguidos: es lo que reparte el trabajo entre hilos."""
    hoy = date.today().isoformat()

    assert httpx.get(f"{server}/api/salud").json()["ok"] is True
    assert len(httpx.get(f"{server}/api/catalogo/ejercicios").json()) >= 50

    routine = httpx.post(
        f"{server}/api/rutinas",
        json={
            "name": "Empuje",
            "exercises": [{"exercise_slug": "flexiones", "spec": {"count": 3, "reps": 15}}],
        },
    )
    assert routine.status_code == 201, routine.text
    routine_id = routine.json()["id"]

    weekday = date.today().weekday()
    week = httpx.put(
        f"{server}/api/semana",
        json={"days": {str(d): (routine_id if d == weekday else None) for d in range(7)}},
    )
    assert week.status_code == 200, week.text

    # Consultar, registrar y volver a consultar: cada llamada puede caer en un
    # hilo distinto del threadpool.
    assert httpx.get(f"{server}/api/hoy").json()["state"] == "pending"
    assert (
        httpx.post(f"{server}/api/sesiones/como-planificado", json={"date": hoy}).status_code == 201
    )
    assert httpx.get(f"{server}/api/hoy").json()["state"] == "done"
    dia = httpx.get(f"{server}/api/dias/{hoy}").json()
    assert dia["scheduled"] and dia["scheduled"][0]["session"] is not None

    year, month = date.today().year, date.today().month
    calendario = httpx.get(f"{server}/api/calendario/{year}/{month}").json()
    assert any(d["date"] == hoy and d["state"] == "done" for d in calendario["days"])


def test_la_pwa_se_sirve_desde_el_mismo_proceso(server):
    """ADR-0001: una sola URL para la interfaz y la API."""
    index = httpx.get(f"{server}/")
    if index.status_code == 404:
        pytest.skip("frontend sin compilar; `npm run build` en frontend/")
    assert '<div id="root">' in index.text
    # Una ruta del router de React no es un fichero: debe devolver el index.
    assert httpx.get(f"{server}/calendario").status_code == 200

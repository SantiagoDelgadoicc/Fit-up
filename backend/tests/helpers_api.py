"""Constantes y atajos para los tests de la API."""

from __future__ import annotations

from datetime import date

SUNDAY = date(2026, 3, 15)
MONDAY = date(2026, 3, 9)
TUESDAY = date(2026, 3, 10)
WEDNESDAY = date(2026, 3, 11)
FRIDAY = date(2026, 3, 13)


def make_routine(client, name="Empuje") -> int:
    response = client.post(
        "/api/rutinas",
        json={
            "name": name,
            "exercises": [
                {"exercise_slug": "flexiones", "spec": {"count": 3, "reps": 15}},
                {
                    "exercise_slug": "press_banca",
                    "spec": {"count": 3, "reps": 8, "weight_kg": 40.0},
                },
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def schedule(client, routine_id: int, days=(0, 2, 4), effective_from="2026-03-01"):
    payload = {
        "days": {str(d): (routine_id if d in days else None) for d in range(7)},
        "effective_from": effective_from,
    }
    response = client.put("/api/semana", json=payload)
    assert response.status_code == 200, response.text
    return response.json()

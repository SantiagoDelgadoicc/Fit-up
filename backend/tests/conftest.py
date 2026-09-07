"""Fixtures compartidas por toda la suite.

Los constructores de entidades viven en `helpers_domain` y `helpers_app`, no
aqui: tres ficheros `conftest.py` en distintos niveles colisionan como modulo
`conftest`, y un import desde los tests acabaria resolviendo al equivocado.
Aqui solo van fixtures, que pytest descubre por si mismo.
"""

from __future__ import annotations

from datetime import date

import pytest


@pytest.fixture
def today() -> date:
    return date(2026, 3, 15)

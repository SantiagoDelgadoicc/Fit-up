"""Avisos de equilibrio muscular.

Lo que se prueba aquí no es la aritmética del cociente, sino las dos promesas
del módulo: que no compara lo que no puede y que no avisa por ruido.
"""

from __future__ import annotations

import pytest

from fitup.domain.ranking.balance import (
    BALANCED_LOW,
    PAIRS,
    BalancePair,
    BalanceVerdict,
    check_balance,
)

PAR = BalancePair(
    key="prueba",
    name="Prueba",
    left_name="Izquierda",
    right_name="Derecha",
    left=("a",),
    right=("b",),
)


def run(a, b, pair=PAR):
    return check_balance({"a": a, "b": b}, pairs=(pair,))[0]


def test_diferencias_pequenas_no_generan_aviso():
    """Un 20 % de diferencia entre antagonistas es normal; avisar sería ruido."""
    assert run(60.0, 50.0).verdict is BalanceVerdict.EQUILIBRADO
    assert run(50.0, 60.0).verdict is BalanceVerdict.EQUILIBRADO


def test_un_lado_muy_por_delante_se_avisa_con_el_lado_debil_nombrado():
    check = run(80.0, 40.0)

    assert check.verdict is BalanceVerdict.DESEQUILIBRIO
    assert check.ratio == 2.0
    assert "Izquierda" in check.message
    assert "derecha" in check.message  # se nombra el lado que falta trabajar


def test_el_aviso_es_simetrico():
    check = run(40.0, 80.0)

    assert check.verdict is BalanceVerdict.DESEQUILIBRIO
    assert "Derecha" in check.message


def test_sin_rango_en_un_lado_no_se_inventa_un_desequilibrio():
    check = run(80.0, None)

    assert check.verdict is BalanceVerdict.SIN_DATOS
    assert check.missing == ("b",)
    assert check.ratio is None


def test_un_lado_a_cero_no_produce_un_cociente_enganoso():
    check = run(50.0, 0.0)

    assert check.verdict is BalanceVerdict.SIN_DATOS
    assert check.ratio is None


def test_basta_un_musculo_con_datos_por_lado():
    """Romboides o deltoide posterior rara vez tienen marca propia.

    Exigir el lado completo dejaría el aviso mudo justo en el caso que más
    importa: alguien que solo entrena empuje.
    """
    par = BalancePair(
        key="p",
        name="P",
        left_name="Empuje",
        right_name="Tirón",
        left=("pectoral", "triceps"),
        right=("dorsal", "romboides"),
    )
    check = check_balance(
        {"pectoral": 80.0, "triceps": None, "dorsal": 30.0, "romboides": None}, pairs=(par,)
    )[0]

    assert check.verdict is BalanceVerdict.DESEQUILIBRIO
    assert check.left_score == 80.0
    assert check.missing == ("triceps", "romboides")


@pytest.mark.parametrize("ratio", [BALANCED_LOW, 1.0, 1 / BALANCED_LOW])
def test_los_bordes_de_la_horquilla_cuentan_como_equilibrio(ratio):
    assert run(50.0 * ratio, 50.0).verdict is BalanceVerdict.EQUILIBRADO


def test_los_pares_vigilados_son_los_que_pedia_el_plan():
    assert {p.key for p in PAIRS} == {"empuje_tiron", "cuadriceps_femoral"}


def test_un_musculo_desconocido_cuenta_como_sin_datos():
    """`development` viene del ranking: un músculo ausente no tiene rango."""
    check = check_balance({}, pairs=(PAR,))[0]

    assert check.verdict is BalanceVerdict.SIN_DATOS
    assert check.missing == ("a", "b")

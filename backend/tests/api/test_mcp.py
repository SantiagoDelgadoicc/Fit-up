"""El servidor MCP: que las tools funcionan y respetan las mismas reglas.

Lo que se prueba aquí no es el protocolo —de eso responde el SDK— sino que
cada tool es de verdad un envoltorio fino sobre los mismos casos de uso: los
permisos, la auditoría y los invariantes tienen que valer igual que por HTTP,
porque por debajo son las mismas funciones (invariante 6).
"""

from __future__ import annotations

import asyncio

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from fitup.api.deps import open_database
from fitup.application.repositories import history
from fitup.application.services import agent as policy
from fitup.infrastructure.seed import catalog
from helpers_api import SUNDAY


@pytest.fixture
def mcp(tmp_path, monkeypatch):
    """Servidor MCP apuntando a una base temporal.

    Se recarga el módulo no hace falta: la ruta se lee de `FITUP_DB` en cada
    llamada, precisamente para que el servidor pueda arrancar antes de que la
    base exista.
    """
    db = tmp_path / "fitup.db"
    conn = open_database(db)
    catalog.seed(conn)
    conn.close()

    monkeypatch.setenv("FITUP_DB", str(db))
    from fitup import mcp_server

    return mcp_server


def _permitir(db_path, *scopes: str) -> None:
    conn = open_database(db_path)
    try:
        valores = dict(policy.DEFAULT_SCOPES) | {s: True for s in scopes}
        history.set_setting(conn, policy.SCOPES_KEY, valores)
        conn.commit()
    finally:
        conn.close()


def _sesion() -> list[dict]:
    return [
        {
            "exercise_slug": "press_banca",
            "sets": [{"set_no": 1, "reps": 8, "weight_kg": 40.0}],
        }
    ]


# ---------------------------------------------------------------- Contrato


def test_las_tools_se_publican_con_su_descripcion(mcp):
    """Un agente descubre lo que puede hacer: sin descripcion no hay descubrimiento."""
    tools = asyncio.run(mcp.servidor.list_tools())
    assert len(tools) >= 16
    assert all(t.description for t in tools)
    assert all(t.input_schema is not None for t in tools)


def test_las_tools_de_texto_libre_avisan_de_la_frontera(mcp):
    """La frontera dato/instruccion tiene que estar donde el modelo la lee.

    En un documento que nunca carga no protege de nada: va en la descripcion de
    cada tool que puede devolver texto escrito por una persona.
    """
    tools = {t.name: t.description for t in asyncio.run(mcp.servidor.list_tools())}
    for nombre in ("consultar_dia", "listar_rutinas", "ver_rutina", "historial"):
        assert "nunca instrucciones" in tools[nombre]


# ----------------------------------------------------------------- Lectura


def test_leer_no_necesita_permisos_extra(mcp):
    """`read` viene activado por defecto: el agente puede mirar desde el minuto uno."""
    ranking = mcp.ranking_muscular()
    assert len(ranking["entries"]) == 18
    assert mcp.listar_rutinas() == []


def test_el_ranking_se_presenta_como_estimacion(mcp):
    """El rango es calibracion provisional (D9) y el agente tiene que saberlo."""
    tools = {t.name: t.description for t in asyncio.run(mcp.servidor.list_tools())}
    assert "ESTIMACIÓN" in tools["ranking_muscular"]
    assert mcp.ranking_muscular()["provisional"] is True


def test_un_musculo_inexistente_da_un_error_claro(mcp):
    """El SDK solo deja llegar al modelo el texto de un ToolError.

    Cualquier otra excepcion le llega como "error inesperado", y con eso el
    agente no puede corregirse.
    """
    with pytest.raises(ToolError, match="biceps_femoral_izquierdo_inventado"):
        mcp.detalle_musculo("biceps_femoral_izquierdo_inventado")


# ------------------------------------------------------------------ Scopes


def test_por_defecto_el_agente_no_escribe_tampoco_por_mcp(mcp, tmp_path):
    """El guardarrail no puede depender de por donde entre el agente.

    Y el motivo tiene que llegarle: un agente al que le dicen "error" no puede
    hacer nada; uno al que le nombran el permiso puede pedirselo al usuario.
    """
    with pytest.raises(ToolError, match="write_sessions"):
        mcp.registrar_entrenamiento(fecha=SUNDAY.isoformat(), ejercicios=_sesion())


def test_con_permiso_escribe_y_queda_registrado(mcp, tmp_path):
    _permitir(tmp_path / "fitup.db", "write_sessions")

    sesion = mcp.registrar_entrenamiento(fecha=SUNDAY.isoformat(), ejercicios=_sesion())
    assert sesion["date"] == SUNDAY.isoformat()

    entradas = mcp.auditoria(actor="agente")
    assert "log_session" in [e["action"] for e in entradas]
    assert all(e["actor"] == "agente" for e in entradas)


def test_un_rechazo_por_mcp_tambien_deja_rastro(mcp):
    with pytest.raises(ToolError):
        mcp.marcar_no_realizado(fecha=SUNDAY.isoformat())

    rechazos = mcp.auditoria(resultado="rechazado")
    assert [e["action"] for e in rechazos] == ["scope:write_sessions"]


def test_los_permisos_se_pueden_consultar_antes_de_intentarlo(mcp):
    """Para planificar sin descubrir el error a mitad de un lote."""
    assert mcp.permisos() == policy.DEFAULT_SCOPES


# ------------------------------------------------------------------ Lotes


def test_el_primer_cambio_del_lote_guarda_copia(mcp, tmp_path):
    _permitir(tmp_path / "fitup.db", "write_sessions")
    mcp.registrar_entrenamiento(fecha=SUNDAY.isoformat(), ejercicios=_sesion())

    assert len(list((tmp_path / "backups").glob("fitup-agente-*.db"))) == 1


def test_las_escrituras_seguidas_no_repiten_la_copia(mcp, tmp_path):
    _permitir(tmp_path / "fitup.db", "write_sessions")
    for dia in ("2026-03-11", "2026-03-12", "2026-03-13"):
        mcp.registrar_entrenamiento(fecha=dia, ejercicios=_sesion())

    assert len(list((tmp_path / "backups").glob("fitup-agente-*.db"))) == 1


# ------------------------------------------------------------- Invariantes


def test_la_idempotencia_evita_duplicar_al_reintentar(mcp, tmp_path):
    """Un agente que reintenta por timeout es el caso normal, no el raro."""
    _permitir(tmp_path / "fitup.db", "write_sessions")
    argumentos = {
        "fecha": SUNDAY.isoformat(),
        "ejercicios": _sesion(),
        "clave_idempotencia": "reintento-1",
    }
    primera = mcp.registrar_entrenamiento(**argumentos)
    segunda = mcp.registrar_entrenamiento(**argumentos)

    assert primera["id"] == segunda["id"]
    assert len(mcp.historial()) == 1


def test_una_entrada_mal_formada_se_explica_en_vez_de_reventar(mcp, tmp_path):
    """El agente tiene que poder corregirse leyendo el error."""
    _permitir(tmp_path / "fitup.db", "write_sessions")
    with pytest.raises(ToolError, match="exercise_slug"):
        mcp.registrar_entrenamiento(fecha=SUNDAY.isoformat(), ejercicios=[{"sets": []}])


def test_registrar_en_el_futuro_se_rechaza_igual_que_por_http(mcp, tmp_path):
    """La regla vive en el caso de uso, así que vale para los dos adaptadores."""
    _permitir(tmp_path / "fitup.db", "write_sessions")
    with pytest.raises(ToolError):
        mcp.registrar_entrenamiento(fecha="2099-01-01", ejercicios=_sesion())


def test_una_fecha_mal_formada_dice_el_formato(mcp):
    """El agente puede escribir "ayer" o "15/03/2026": el error tiene que guiarle."""
    with pytest.raises(ToolError, match="AAAA-MM-DD"):
        mcp.consultar_dia(fecha="ayer")

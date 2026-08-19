"""Pruebas de `api.imports_process._process` (la frontera HTTP real).

Cero red, cero psycopg real, cero Postgres real: `connect`/`storage_factory`
se inyectan igual que `conn`/`storage` en `engine.pipeline.run_import_job`
(mismo criterio que `tests/python/conftest.py`). `run_import_job` se
reemplaza directamente por un doble: lo que hace *ese* módulo cuando todo
sale bien o mal ya está cubierto por `test_pipeline.py`; aquí interesa solo
la capa de arriba — variables de entorno, logging, y que un fallo nunca deje
un `import_job` en `pending` sin rastro cuando hay conexión disponible.
"""

from __future__ import annotations

import email.message
import io
import logging
from typing import Any

import pytest

from conftest import FakeConnection

import api.imports_process as imports_process
from engine.persistence import PersistResult

JOB_ID = "job-1"


class ClosableFakeConnection(FakeConnection):
    """`FakeConnection` + `close()`, que `_process` sí necesita llamar."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.closed = False

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _todas_las_variables_configuradas(monkeypatch: pytest.MonkeyPatch) -> None:
    """Estado feliz por defecto; cada prueba desconfigura lo que necesita."""
    monkeypatch.setenv("SUPABASE_URL", "https://proyecto.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://servicio/db")


def _no_deberia_llamarse(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("no debería haberse invocado en este camino")


# --------------------------------------------------------------------------- #
# Variables de entorno faltantes
# --------------------------------------------------------------------------- #


def test_falta_supabase_db_url_no_promete_mark_failed(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.setattr(imports_process, "run_import_job", _no_deberia_llamarse)

    with caplog.at_level(logging.ERROR, logger="imports_process"):
        status, body = imports_process._process(JOB_ID, connect=_no_deberia_llamarse)

    assert status == 500
    assert "SUPABASE_DB_URL" in body["error"]
    assert any("SUPABASE_DB_URL" in record.getMessage() for record in caplog.records)


def test_falta_supabase_url_pero_hay_db_url_marca_failed_best_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setattr(imports_process, "run_import_job", _no_deberia_llamarse)

    conn = ClosableFakeConnection()
    status, body = imports_process._process(JOB_ID, connect=lambda: conn)

    assert status == 500
    assert "SUPABASE_URL" in body["error"]
    assert conn.wrote_to("import_jobs")  # el UPDATE ... status = 'failed' quedó confirmado
    assert conn.closed


def test_falta_supabase_url_y_el_connect_de_respaldo_tambien_falla_no_revienta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setattr(imports_process, "run_import_job", _no_deberia_llamarse)

    def connect_roto() -> Any:
        raise RuntimeError("no hay red hacia Postgres")

    status, body = imports_process._process(JOB_ID, connect=connect_roto)

    assert status == 500
    assert "SUPABASE_URL" in body["error"]


# --------------------------------------------------------------------------- #
# Fallo al conectar con todas las variables presentes
# --------------------------------------------------------------------------- #


def test_fallo_de_conexion_no_promete_mark_failed(caplog: pytest.LogCaptureFixture) -> None:
    def connect_roto() -> Any:
        raise RuntimeError("password authentication failed")

    with caplog.at_level(logging.ERROR, logger="imports_process"):
        status, body = imports_process._process(JOB_ID, connect=connect_roto)

    assert status == 500
    assert "No se pudo conectar a la base" in body["error"]
    assert any("password authentication failed" in record.getMessage() for record in caplog.records)


# --------------------------------------------------------------------------- #
# `run_import_job` explota sin control (el caso que antes dejaba `pending`)
# --------------------------------------------------------------------------- #


def test_excepcion_no_controlada_marca_failed_con_la_conexion_ya_abierta(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    conn = ClosableFakeConnection()

    def run_import_job_roto(job_id: Any, *, conn: Any, storage: Any) -> Any:
        raise RuntimeError("no existe la importación o falló la consulta")

    monkeypatch.setattr(imports_process, "run_import_job", run_import_job_roto)

    with caplog.at_level(logging.ERROR, logger="imports_process"):
        status, body = imports_process._process(JOB_ID, connect=lambda: conn)

    assert status == 500
    assert body["error"]  # readable_error(...) siempre produce texto no vacío
    assert conn.wrote_to("import_jobs")  # quedó 'failed', no 'pending' para siempre
    assert conn.rollbacks >= 1  # se limpia la transacción antes de marcar failed
    assert conn.closed


def test_excepcion_no_controlada_no_expone_detalle_crudo_si_mark_failed_tambien_falla(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Si hasta el propio `mark_failed` falla, la respuesta HTTP igual sale."""
    conn = ClosableFakeConnection(fail_on="UPDATE import_jobs")

    def run_import_job_roto(job_id: Any, *, conn: Any, storage: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(imports_process, "run_import_job", run_import_job_roto)

    with caplog.at_level(logging.ERROR, logger="imports_process"):
        status, body = imports_process._process(JOB_ID, connect=lambda: conn)

    assert status == 500
    assert body["error"]
    assert conn.closed
    assert any("no se pudo marcar failed" in record.getMessage() for record in caplog.records)


# --------------------------------------------------------------------------- #
# Camino feliz y camino de negocio fallido: `_process` solo reporta, no marca
# --------------------------------------------------------------------------- #


def test_camino_feliz_200_y_cierra_conexion(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = ClosableFakeConnection()
    storage_calls: list[tuple[str, str]] = []

    def run_import_job_ok(job_id: Any, *, conn: Any, storage: Any) -> PersistResult:
        return PersistResult(
            import_job_id=job_id, status="completed", lines_inserted=10, issues_inserted=0
        )

    def storage_factory(base_url: str, service_role_key: str) -> Any:
        storage_calls.append((base_url, service_role_key))
        return object()

    monkeypatch.setattr(imports_process, "run_import_job", run_import_job_ok)

    status, body = imports_process._process(
        JOB_ID, connect=lambda: conn, storage_factory=storage_factory
    )

    assert status == 200
    assert body == {
        "importJobId": JOB_ID,
        "status": "completed",
        "linesInserted": 10,
        "issuesInserted": 0,
        "errorMessage": None,
    }
    assert conn.closed
    assert storage_calls == [("https://proyecto.supabase.co", "service-role-key")]


def test_fallo_de_negocio_ya_manejado_por_pipeline_da_422_y_no_marca_failed_de_nuevo(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    conn = ClosableFakeConnection()

    def run_import_job_failed(job_id: Any, *, conn: Any, storage: Any) -> PersistResult:
        # `engine.pipeline.run_import_job` YA marcó failed antes de retornar
        # (cubierto en test_pipeline.py); acá solo se simula el retorno.
        return PersistResult(
            import_job_id=job_id, status="failed", error_message="Columnas faltantes."
        )

    monkeypatch.setattr(imports_process, "run_import_job", run_import_job_failed)

    with caplog.at_level(logging.WARNING, logger="imports_process"):
        status, body = imports_process._process(JOB_ID, connect=lambda: conn)

    assert status == 422
    assert body["errorMessage"] == "Columnas faltantes."
    assert conn.closed
    assert any("Columnas faltantes" in record.getMessage() for record in caplog.records)


# --------------------------------------------------------------------------- #
# `handler.do_POST` — el 401 real (autenticación entre servidores)
# --------------------------------------------------------------------------- #
#
# `BaseHTTPRequestHandler.__init__` intenta atender la petición de inmediato
# sobre un socket real; para probar `do_POST` en aislamiento se construye la
# instancia sin pasar por `__init__` (`__new__`) y se le da lo mínimo que usa:
# `headers` (case-insensitive, como el `http.client.HTTPMessage` real) y
# `rfile`. `_json` se reemplaza para capturar la respuesta sin tocar sockets.


def _make_handler(*, headers: dict[str, str], body: bytes = b"") -> Any:
    instance = imports_process.handler.__new__(imports_process.handler)
    message = email.message.Message()
    for name, value in headers.items():
        message[name] = value
    instance.headers = message
    instance.rfile = io.BytesIO(body)
    instance._responses: list[tuple[int, dict]] = []
    instance._json = lambda status, resp_body: instance._responses.append((status, resp_body))
    return instance


def test_do_post_401_sin_internal_api_secret_configurado(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("INTERNAL_API_SECRET", raising=False)
    instance = _make_handler(headers={"x-internal-secret": "lo-que-sea"})

    with caplog.at_level(logging.WARNING, logger="imports_process"):
        instance.do_POST()

    assert instance._responses == [(401, {"error": "No autorizado."})]
    [record] = [r for r in caplog.records if "401" in r.getMessage()]
    assert "configurado=False" in record.getMessage()
    assert "presente=True" in record.getMessage()
    # Nunca se loguea el valor real de ningún secreto.
    assert "lo-que-sea" not in caplog.text


def test_do_post_401_con_secret_configurado_y_header_ausente(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "el-secreto-real")
    instance = _make_handler(headers={})  # nada de x-internal-secret

    with caplog.at_level(logging.WARNING, logger="imports_process"):
        instance.do_POST()

    assert instance._responses == [(401, {"error": "No autorizado."})]
    [record] = [r for r in caplog.records if "401" in r.getMessage()]
    assert "configurado=True" in record.getMessage()
    assert "presente=False" in record.getMessage()
    assert "el-secreto-real" not in caplog.text


def test_do_post_401_con_secret_configurado_y_header_incorrecto(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "el-secreto-real")
    instance = _make_handler(headers={"x-internal-secret": "otro-valor"})

    with caplog.at_level(logging.WARNING, logger="imports_process"):
        instance.do_POST()

    assert instance._responses == [(401, {"error": "No autorizado."})]
    [record] = [r for r in caplog.records if "401" in r.getMessage()]
    assert "configurado=True" in record.getMessage()
    assert "presente=True" in record.getMessage()  # llegó, pero no coincide
    assert "el-secreto-real" not in caplog.text
    assert "otro-valor" not in caplog.text


def test_do_post_secret_correcto_no_loguea_401_y_llega_a_process(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "el-secreto-real")
    instance = _make_handler(
        headers={
            "x-internal-secret": "el-secreto-real",
            "content-length": str(len(b'{"jobId": "job-1"}')),
        },
        body=b'{"jobId": "job-1"}',
    )
    monkeypatch.setattr(
        imports_process, "_process", lambda job_id, **kwargs: (200, {"importJobId": job_id})
    )

    with caplog.at_level(logging.WARNING, logger="imports_process"):
        instance.do_POST()

    assert instance._responses == [(200, {"importJobId": "job-1"})]
    assert not any("401" in record.getMessage() for record in caplog.records)

"""Persistencia transaccional de una importación (contrato §8 y §9.2/§9.3).

Una sola función pública hace el trabajo de las tres importaciones
(:func:`persist_import`); lo que varía entre ellas está declarado en
:data:`TARGETS`, no repartido en tres copias del mismo manejo de rollback —
que es exactamente donde se cuelan los fallos parciales que el contrato §9.3
prohíbe.

Garantías que implementa:

1. **Todo o nada.** Marcar `processing`, dejar `superseded` la cabecera
   anterior, insertar cabecera + líneas + incidencias y pasar el trabajo a
   `completed` ocurre en **una** transacción. Cualquier excepción hace
   ``rollback``: no queda ninguna fila nueva vigente.
2. **El fallo se registra igual.** Tras el ``rollback``, en una transacción
   **separada**, el trabajo pasa a `failed` con un ``error_message`` legible en
   español y se guardan las incidencias acumuladas (son el diagnóstico). Si ese
   segundo intento también falla, se relanza el error original encadenado: no
   se traga nunca.
3. **Un `import_job` terminal no se reutiliza.** Si el trabajo ya está
   `completed` o `failed`, se rechaza antes de tocar nada; un reintento exige
   crear un `import_jobs` nuevo (contrato §8). Esa validación vive aquí, no
   solo en la ruta HTTP.

**No se abre ninguna conexión en este módulo.** La conexión se inyecta y solo
se le exige la interfaz DB-API 2.0 (``cursor()``, ``execute``, ``executemany``,
``fetchone``, ``fetchall``, ``commit``, ``rollback``) con marcador de posición
``%s`` — compatible con psycopg 3 y psycopg 2 sin depender de ninguna de las
dos, y sustituible por un doble en memoria en las pruebas. `engine/` nunca lee
credenciales ni variables de entorno.

Nota de despliegue para quien conecte la ruta: `sales_*` e `inventory_*` son
**escritura exclusiva de `service_role`** (contrato §7), así que la conexión
inyectada debe ser de servidor, nunca la del navegador.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from engine.imports import ImportType, PreparedImport
from engine.validation import ImportIssue, ValidationError

__all__ = [
    "ImportTarget",
    "TARGETS",
    "PersistResult",
    "persist_import",
    "mark_failed",
    "TERMINAL_JOB_STATUSES",
]

#: Estados desde los que un `import_jobs` ya no puede procesarse otra vez.
TERMINAL_JOB_STATUSES: frozenset[str] = frozenset({"completed", "failed"})

#: Longitud máxima que se guarda en `import_jobs.error_message`. Un traceback
#: entero no es un mensaje legible; el detalle fino va en `import_issues`.
MAX_ERROR_MESSAGE = 2000

#: Columnas que necesitan un cast explícito en el ``INSERT``.
_COLUMN_CASTS: dict[str, str] = {"raw": "::jsonb"}


# --------------------------------------------------------------------------- #
# Configuración declarativa por tipo de importación
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ImportTarget:
    """Dónde y cómo aterriza una importación de un tipo dado.

    Los nombres de tabla y de columna son literalmente los del contrato §6.3;
    ninguno viene de datos del usuario, así que se interpolan en el SQL sin
    riesgo de inyección (los **valores** siempre van por parámetro).
    """

    job_type: str
    header_table: str
    header_columns: tuple[str, ...]
    line_table: str
    line_fk: str
    line_columns: tuple[str, ...]
    #: Columnas de la cabecera que identifican "la misma importación" y cuya
    #: versión anterior `active` hay que dejar `superseded` (contrato §9.2).
    supersede_keys: tuple[str, ...]
    #: `price_lists` nace `draft` y se activa al final: una lista no-draft es
    #: inmutable por trigger (§9.1) y no admitiría que se le inserten ítems.
    initial_status: str = "active"
    activate_after_lines: bool = False
    #: Numeración `max(version) + 1` por proveedor, calculada en la transacción.
    versioned_by: str | None = None


TARGETS: dict[str, ImportTarget] = {
    ImportType.INVEPTOS_SALES: ImportTarget(
        job_type=ImportType.INVEPTOS_SALES,
        header_table="sales_imports",
        header_columns=(
            "import_job_id",
            "supplier_id",
            "period_start",
            "period_end",
            "status",
            "created_by",
        ),
        line_table="sales_lines",
        line_fk="sales_import_id",
        line_columns=(
            "sales_import_id",
            "ean",
            "location_id",
            "product_id",
            "units_sold",
            "tbc_cost",
            "source_row_number",
        ),
        supersede_keys=("supplier_id", "period_start", "period_end"),
    ),
    ImportType.SDOS_INVENTORY: ImportTarget(
        job_type=ImportType.SDOS_INVENTORY,
        header_table="inventory_snapshots",
        header_columns=("import_job_id", "snapshot_date", "fair_mode", "status"),
        line_table="inventory_lines",
        line_fk="snapshot_id",
        line_columns=(
            "snapshot_id",
            "ean",
            "tbc_sku",
            "location_id",
            "on_hand",
            "pvp",
            "supplier_tbc_code",
        ),
        supersede_keys=("snapshot_date",),
    ),
    ImportType.SUPPLIER_PRICE_LIST: ImportTarget(
        job_type=ImportType.SUPPLIER_PRICE_LIST,
        header_table="price_lists",
        header_columns=(
            "import_job_id",
            "supplier_id",
            "source_file_id",
            "version",
            "effective_date",
            "status",
            "supersedes_id",
        ),
        line_table="price_list_items",
        line_fk="price_list_id",
        line_columns=(
            "price_list_id",
            "supplier_product_id",
            "ean",
            "supplier_cost",
            "source_row_number",
            "raw",
        ),
        supersede_keys=("supplier_id",),
        initial_status="draft",
        activate_after_lines=True,
        versioned_by="supplier_id",
    ),
}

ISSUE_COLUMNS: tuple[str, ...] = (
    "import_job_id",
    "file_id",
    "severity",
    "code",
    "source",
    "row_number",
    "ean",
    "sku",
    "product_name",
    "detail",
)


# --------------------------------------------------------------------------- #
# Resultado
# --------------------------------------------------------------------------- #


@dataclass
class PersistResult:
    """Qué pasó con la importación. ``status`` es el de `import_jobs`.

    Un fallo previsto (violación de constraint, ubicación desconocida, caída de
    la base a mitad de la inserción) **no se relanza**: es un desenlace normal
    del contrato §8, se refleja en ``status='failed'`` con ``error_message`` y
    el llamador decide qué responder. La excepción original queda en ``error``
    para poder registrarla en el log del servidor.
    """

    import_job_id: Any
    status: str
    header_id: Any = None
    lines_inserted: int = 0
    issues_inserted: int = 0
    superseded_id: Any = None
    version: int | None = None
    error_message: str | None = None
    error: BaseException | None = field(default=None, repr=False)

    @property
    def ok(self) -> bool:
        return self.status == "completed"


# --------------------------------------------------------------------------- #
# API pública
# --------------------------------------------------------------------------- #


def persist_import(
    conn: Any,
    *,
    import_job_id: Any,
    prepared: PreparedImport,
    file_id: Any = None,
    supplier_id: Any = None,
    created_by: Any = None,
) -> PersistResult:
    """Guarda una importación completa o no guarda nada.

    ``supplier_id``/``file_id``/``created_by`` son el contexto que conoce la
    ruta que llama (no el archivo). ``supplier_id`` es obligatorio para una
    lista de precios y opcional para ventas e inventario.

    Lanza ``ValidationError`` **antes de escribir nada** si el tipo no está
    soportado o si el `import_job` no existe o ya es terminal. Cualquier otro
    fallo se traduce a ``status='failed'`` (ver :class:`PersistResult`).
    """
    target = TARGETS.get(prepared.job_type)
    if target is None:
        raise ValidationError(
            f"Tipo de importación no soportado: '{prepared.job_type}'. "
            f"Válidos: {', '.join(sorted(TARGETS))}."
        )
    if target.versioned_by and supplier_id is None:
        raise ValidationError(
            "Una lista de precios necesita el proveedor (supplier_id) para "
            "numerar su versión y dejar la anterior superseded."
        )

    _require_reusable_job(conn, import_job_id)

    result = PersistResult(import_job_id=import_job_id, status="processing")
    try:
        cursor = conn.cursor()
        try:
            _execute(
                cursor,
                "UPDATE import_jobs SET status = 'processing', started_at = now() "
                "WHERE id = %s",
                (import_job_id,),
            )

            header = dict(prepared.header)
            header["import_job_id"] = import_job_id
            header["status"] = target.initial_status
            if "supplier_id" in target.header_columns and supplier_id is not None:
                header["supplier_id"] = supplier_id
            if "created_by" in target.header_columns:
                header["created_by"] = created_by
            if "source_file_id" in target.header_columns:
                header["source_file_id"] = file_id

            result.superseded_id = _supersede_previous(cursor, target, header)
            if "supersedes_id" in target.header_columns:
                header["supersedes_id"] = result.superseded_id
            if target.versioned_by:
                result.version = _next_version(cursor, target, header)
                header["version"] = result.version

            result.header_id = _insert_header(cursor, target, header)
            result.lines_inserted = _insert_lines(
                cursor, target, prepared.lines, result.header_id
            )
            result.issues_inserted = _insert_issues(
                cursor, prepared.issues, import_job_id=import_job_id, file_id=file_id
            )

            if target.activate_after_lines:
                _execute(
                    cursor,
                    f"UPDATE {target.header_table} SET status = 'active' WHERE id = %s",
                    (result.header_id,),
                )

            _complete_job(cursor, import_job_id, prepared)
        finally:
            _close(cursor)
        conn.commit()
    except Exception as exc:  # noqa: BLE001 - se traduce a `failed`, no se traga
        _rollback(conn)
        message = readable_error(exc)
        mark_failed(
            conn,
            import_job_id=import_job_id,
            error_message=message,
            issues=prepared.issues,
            file_id=file_id,
            original=exc,
        )
        return PersistResult(
            import_job_id=import_job_id,
            status="failed",
            error_message=message,
            error=exc,
        )

    result.status = "completed"
    return result


def mark_failed(
    conn: Any,
    *,
    import_job_id: Any,
    error_message: str,
    issues: Iterable[ImportIssue] = (),
    file_id: Any = None,
    original: BaseException | None = None,
) -> None:
    """Marca `failed` un trabajo, en su **propia** transacción.

    Se expone aparte de :func:`persist_import` para que la ruta pueda usarla
    ante un fallo anterior al parseo (archivo ilegible, columnas faltantes,
    ``InvalidPeriodError``), donde no hay nada preparado que guardar.

    Si el marcado también falla, se relanza: ``original`` encadenado si se pasó
    (es el error que de verdad importa), o el fallo del marcado en su defecto.
    """
    try:
        cursor = conn.cursor()
        try:
            _execute(
                cursor,
                "UPDATE import_jobs SET status = 'failed', error_message = %s, "
                "finished_at = now() WHERE id = %s",
                (_truncate(error_message), import_job_id),
            )
            _insert_issues(cursor, issues, import_job_id=import_job_id, file_id=file_id)
        finally:
            _close(cursor)
        conn.commit()
    except Exception as marking_error:  # noqa: BLE001
        _rollback(conn)
        if original is not None:
            raise original from marking_error
        raise


def readable_error(exc: BaseException) -> str:
    """Mensaje para `import_jobs.error_message`, legible por quien importa.

    Un ``ValidationError`` ya trae un mensaje escrito para el usuario y se usa
    tal cual. Cualquier otro error (constraint violada, conexión caída) se
    envuelve explicando lo único que al usuario le importa saber: que no quedó
    nada a medias.
    """
    if isinstance(exc, ValidationError):
        return _truncate(str(exc))
    detail = str(exc).strip() or exc.__class__.__name__
    return _truncate(
        "La importación falló al guardar los datos y se revirtió completa: "
        f"{detail}. No quedó ninguna fila parcial; corrija el archivo o reintente "
        "creando una importación nueva."
    )


# --------------------------------------------------------------------------- #
# Pasos internos
# --------------------------------------------------------------------------- #


def _require_reusable_job(conn: Any, import_job_id: Any) -> None:
    """Rechaza un `import_job` inexistente o ya terminal, sin escribir nada."""
    cursor = conn.cursor()
    try:
        _execute(cursor, "SELECT status FROM import_jobs WHERE id = %s", (import_job_id,))
        row = cursor.fetchone()
    finally:
        _close(cursor)

    if row is None:
        raise ValidationError(
            f"No existe la importación {import_job_id}: no hay dónde guardar el resultado."
        )
    status = _first(row)
    if status in TERMINAL_JOB_STATUSES:
        raise ValidationError(
            f"La importación {import_job_id} ya está en estado '{status}' y no se "
            "reprocesa. Un reintento debe crear una importación nueva."
        )


def _supersede_previous(
    cursor: Any, target: ImportTarget, header: Mapping[str, Any]
) -> Any:
    """Deja `superseded` la cabecera `active` equivalente; devuelve su id.

    Es un cambio de **estado**, nunca un borrado: una corrida histórica sigue
    apuntando por id a la cabecera original y su `fk restrict` la protege
    (contrato §9.2). El índice único parcial ``where status = 'active'`` de la
    migración es la red de seguridad de esta operación, no su reemplazo: aquí
    vive la lógica porque solo aquí se sabe qué período/proveedor se reemplaza.
    """
    if not target.supersede_keys:
        return None

    conditions = []
    params: list[Any] = []
    for key in target.supersede_keys:
        value = header.get(key)
        if value is None:
            # `IS NOT DISTINCT FROM` para que NULL = NULL (ventas sin proveedor).
            conditions.append(f"{key} IS NULL")
        else:
            conditions.append(f"{key} IS NOT DISTINCT FROM %s")
            params.append(value)

    _execute(
        cursor,
        f"UPDATE {target.header_table} SET status = 'superseded' "
        f"WHERE status = 'active' AND {' AND '.join(conditions)} RETURNING id",
        tuple(params),
    )
    row = cursor.fetchone()
    return _first(row) if row else None


def _next_version(cursor: Any, target: ImportTarget, header: Mapping[str, Any]) -> int:
    """``max(version) + 1`` del proveedor, serializado por bloqueo de fila.

    No se usa ``SELECT max(version) ... FOR UPDATE`` porque Postgres no admite
    ``FOR UPDATE`` junto a una función de agregación. Se bloquea la fila de la
    versión más alta, que serializa a dos importaciones concurrentes del mismo
    proveedor. Si el proveedor no tiene ninguna lista todavía no hay fila que
    bloquear y dos concurrentes podrían pedir la versión 1: ahí actúa
    ``unique (supplier_id, version)`` y la perdedora termina en `failed` con
    mensaje, que es el desenlace correcto.
    """
    key = target.versioned_by
    assert key is not None  # garantizado por el llamador
    _execute(
        cursor,
        f"SELECT version FROM {target.header_table} WHERE {key} = %s "
        "ORDER BY version DESC LIMIT 1 FOR UPDATE",
        (header.get(key),),
    )
    row = cursor.fetchone()
    current = _first(row) if row else None
    return int(current) + 1 if current is not None else 1


def _insert_header(cursor: Any, target: ImportTarget, header: Mapping[str, Any]) -> Any:
    columns = target.header_columns
    _execute(
        cursor,
        f"INSERT INTO {target.header_table} ({', '.join(columns)}) "
        f"VALUES ({_placeholders(columns)}) RETURNING id",
        tuple(header.get(column) for column in columns),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValidationError(
            f"La base no devolvió el id de la cabecera insertada en {target.header_table}."
        )
    return _first(row)


def _insert_lines(
    cursor: Any,
    target: ImportTarget,
    lines: Sequence[Mapping[str, Any]],
    header_id: Any,
) -> int:
    if not lines:
        return 0

    locations = _load_locations(cursor) if _needs_locations(target) else {}
    columns = target.line_columns
    rows: list[tuple[Any, ...]] = []
    for line in lines:
        values: list[Any] = []
        for column in columns:
            if column == target.line_fk:
                values.append(header_id)
            elif column == "location_id":
                values.append(_location_id(locations, line))
            elif column == "raw":
                raw = line.get("raw")
                values.append(None if raw is None else json.dumps(raw, ensure_ascii=False))
            else:
                values.append(line.get(column))
        rows.append(tuple(values))

    cursor.executemany(
        f"INSERT INTO {target.line_table} ({', '.join(columns)}) "
        f"VALUES ({_placeholders(columns)})",
        rows,
    )
    return len(rows)


def _insert_issues(
    cursor: Any,
    issues: Iterable[ImportIssue],
    *,
    import_job_id: Any,
    file_id: Any,
) -> int:
    records = [issue.as_dict() for issue in issues]
    if not records:
        return 0
    rows = [
        tuple(
            import_job_id
            if column == "import_job_id"
            else file_id
            if column == "file_id"
            else record.get(column)
            for column in ISSUE_COLUMNS
        )
        for record in records
    ]
    cursor.executemany(
        f"INSERT INTO import_issues ({', '.join(ISSUE_COLUMNS)}) "
        f"VALUES ({_placeholders(ISSUE_COLUMNS)})",
        rows,
    )
    return len(rows)


def _complete_job(cursor: Any, import_job_id: Any, prepared: PreparedImport) -> None:
    """Cierra el trabajo como `completed`.

    ``period_days`` no se escribe: es ``generated always ... stored`` en
    `import_jobs` (contrato §6.3) y Postgres rechaza que se le asigne valor.
    """
    assignments = [
        "status = 'completed'",
        "finished_at = now()",
        "error_message = NULL",
        "rows_total = %s",
        "rows_valid = %s",
        "rows_rejected = %s",
    ]
    params: list[Any] = [
        prepared.rows_total,
        prepared.rows_valid,
        prepared.rows_rejected,
    ]
    if prepared.period_start is not None and prepared.period_end is not None:
        assignments += ["period_start = %s", "period_end = %s"]
        params += [prepared.period_start, prepared.period_end]
    params.append(import_job_id)

    _execute(
        cursor,
        f"UPDATE import_jobs SET {', '.join(assignments)} WHERE id = %s",
        tuple(params),
    )


# --------------------------------------------------------------------------- #
# Catálogo de ubicaciones
# --------------------------------------------------------------------------- #


def _needs_locations(target: ImportTarget) -> bool:
    return "location_id" in target.line_columns


def _load_locations(cursor: Any) -> dict[str, Any]:
    """``locations.name`` → id, en **una** consulta por transacción.

    El catálogo Python (`engine.readers.TISUC_TO_LOCATION`) y las 9 filas de
    `0003_locations.sql` son espejo, así que un nombre ausente significa que
    los dos se desincronizaron: se aborta la importación en vez de guardar
    inventario o ventas sin ubicación.
    """
    _execute(cursor, "SELECT id, name FROM locations", ())
    catalog: dict[str, Any] = {}
    for row in cursor.fetchall() or ():
        identifier, name = row[0], row[1]
        catalog[str(name)] = identifier
    return catalog


def _location_id(catalog: Mapping[str, Any], line: Mapping[str, Any]) -> Any:
    name = line.get("location_name")
    if name in catalog:
        return catalog[name]
    raise ValidationError(
        f"La ubicación '{name}' no existe en el catálogo `locations` de la base. "
        "La importación se canceló completa para no guardar ventas o inventario "
        "sin ubicación."
    )


# --------------------------------------------------------------------------- #
# Utilidades DB-API
# --------------------------------------------------------------------------- #


def _placeholders(columns: Sequence[str]) -> str:
    return ", ".join("%s" + _COLUMN_CASTS.get(column, "") for column in columns)


def _execute(cursor: Any, sql: str, params: Sequence[Any] = ()) -> None:
    cursor.execute(sql, tuple(params))


def _close(cursor: Any) -> None:
    closer = getattr(cursor, "close", None)
    if callable(closer):
        closer()


def _rollback(conn: Any) -> None:
    """``rollback`` defensivo: si la conexión ya murió, no tapar el error real."""
    try:
        conn.rollback()
    except Exception:  # noqa: BLE001 - el error original es el que importa
        pass


def _first(row: Any) -> Any:
    if row is None:
        return None
    if isinstance(row, Mapping):
        return next(iter(row.values()), None)
    if isinstance(row, (list, tuple)):
        return row[0] if row else None
    return row


def _truncate(message: str, limit: int = MAX_ERROR_MESSAGE) -> str:
    text = " ".join(str(message).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"

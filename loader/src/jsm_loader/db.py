from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from importlib import resources

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from .pipeline import LoadData
from .report import validation_report
from .review_design import REF_TABLES, REVIEW_FIELDS
from .tickets import TICKET_COLUMNS

log = logging.getLogger(__name__)

SCHEMA = "jira_ai"

TABLES = (
    "jira_requests",
    "ref_categories",
    "ref_score_anchors",
    "ref_agent_archetypes",
    "ref_evidence_basis",
    "ref_knowledge_deflection_anchors",
    "dim_category",
    "dim_score_anchor",
    "dim_agent_archetype",
    "dim_evidence_basis",
    "dim_knowledge_deflection_anchor",
    "fact_jira_request",
)

_REF_KEYS = {
    "ref_categories": "category_no",
    "ref_score_anchors": "score",
    "ref_agent_archetypes": "archetype_no",
    "ref_evidence_basis": "value",
    "ref_knowledge_deflection_anchors": "score",
}
_STAGE_COLUMNS = (
    "batch_id",
    "source_row_number",
    *TICKET_COLUMNS,
    "validation_status",
    "validation_message",
)
_FIELD_COLUMNS = {"exclude": "is_excluded"}


@dataclass(frozen=True)
class LoadResult:
    batch_id: uuid.UUID
    counts: dict[str, int]
    quarantined: int


def load(
    conn: psycopg.Connection, data: LoadData, analyst_user: str, analyst_password: str
) -> LoadResult:
    batch_id = uuid.uuid4()
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(_script("schema.sql"))
        cur.execute("SELECT set_config('jira_ai.batch_id', %s, true)", (str(batch_id),))
        _copy(
            cur,
            "load_jira_requests_raw",
            ("batch_id", "source_file_name", "source_row_number", "source_payload"),
            (
                (batch_id, data.source_file, row.number, _json(row.values))
                for row in data.tickets.rows
            ),
        )
        _copy(
            cur,
            "load_reference_rows_raw",
            ("batch_id", "source_file_name", "source_label", "source_row_number", "source_payload"),
            (
                (batch_id, data.source_file, row.label, row.row_number, _json(row.payload))
                for row in data.review_design.raw_rows
            ),
        )
        for table in REF_TABLES:
            records = data.review_design.tables.get(table.name, [])
            _copy(
                cur,
                f"stg_{table.name}",
                ("batch_id", *table.columns),
                ((batch_id, *(record[column] for column in table.columns)) for record in records),
            )
        cur.execute(_script("merge_refs.sql"))
        _copy(
            cur,
            "stg_jira_requests",
            _STAGE_COLUMNS,
            (
                (batch_id, *(row[column] for column in _STAGE_COLUMNS[1:]))
                for row in data.staging.rows
            ),
        )
        for level, line in validation_report(data, _ref_keys(cur)):
            log.log(level, "validation: %s", line)
        cur.execute(_merge_tickets())
        cur.execute(_script("merge_facts.sql"))
        _comment_columns(cur, data.review_design.tables.get(REVIEW_FIELDS.name, []))
        _grant_read_only(cur, analyst_user, analyst_password)
        return LoadResult(batch_id, _row_counts(cur), len(data.staging.quarantined))


def _script(name: str) -> str:
    return (resources.files("jsm_loader") / "sql" / name).read_text(encoding="utf-8")


def _table(name: str) -> sql.Identifier:
    return sql.Identifier(SCHEMA, name)


def _json_default(value: object) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _json(values: dict[str, object]) -> Jsonb:
    return Jsonb(values, dumps=lambda obj: json.dumps(obj, default=_json_default))


def _copy(
    cur: psycopg.Cursor,
    table: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[object]],
) -> None:
    statement = sql.SQL("COPY {} ({}) FROM STDIN").format(
        _table(table), sql.SQL(", ").join(map(sql.Identifier, columns))
    )
    with cur.copy(statement) as copy:
        for row in rows:
            copy.write_row(row)


def _ref_keys(cur: psycopg.Cursor) -> dict[str, list[object]]:
    keys: dict[str, list[object]] = {}
    for table, column in _REF_KEYS.items():
        cur.execute(
            sql.SQL("SELECT {} FROM {} ORDER BY 1").format(sql.Identifier(column), _table(table))
        )
        keys[table] = [value for (value,) in cur.fetchall()]
    return keys


def _merge_tickets() -> sql.Composed:
    columns = sql.SQL(", ").join(map(sql.Identifier, TICKET_COLUMNS))
    updates = sql.SQL(", ").join(
        sql.SQL("{0} = excluded.{0}").format(sql.Identifier(column))
        for column in TICKET_COLUMNS
        if column != "key"
    )
    return sql.SQL(
        "INSERT INTO {target} ({columns}, loaded_batch_id) "
        "SELECT {columns}, batch_id FROM {staging} "
        "WHERE batch_id = current_setting('jira_ai.batch_id')::uuid "
        "AND validation_status = 'VALID' "
        "ON CONFLICT (key) DO UPDATE SET {updates}, "
        "loaded_batch_id = excluded.loaded_batch_id, loaded_at = now()"
    ).format(
        target=_table("jira_requests"),
        staging=_table("stg_jira_requests"),
        columns=columns,
        updates=updates,
    )


def _comment_columns(cur: psycopg.Cursor, review_fields: Iterable[dict[str, object]]) -> None:
    for record in review_fields:
        field = str(record["field"])
        column = _FIELD_COLUMNS.get(field, field)
        if column not in TICKET_COLUMNS:
            log.warning(
                "review field '%s' is not a jira_requests column, so it gets no comment", field
            )
            continue
        if record["notes"] is None:
            continue
        cur.execute(
            sql.SQL("COMMENT ON COLUMN {} IS {}").format(
                sql.Identifier(SCHEMA, "jira_requests", column), sql.Literal(record["notes"])
            )
        )


def _grant_read_only(cur: psycopg.Cursor, user: str, password: str) -> None:
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (user,))
    verb = "ALTER" if cur.fetchone() else "CREATE"
    role = sql.Identifier(user)
    schema = sql.Identifier(SCHEMA)
    cur.execute(
        sql.SQL("{} ROLE {} LOGIN PASSWORD {}").format(sql.SQL(verb), role, sql.Literal(password))
    )
    cur.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(schema, role))
    cur.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(schema, role))
    cur.execute(sql.SQL("ALTER ROLE {} SET search_path = {}, public").format(role, schema))


def _row_counts(cur: psycopg.Cursor) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in TABLES:
        cur.execute(sql.SQL("SELECT count(*) FROM {}").format(_table(table)))
        (counts[table],) = cur.fetchone()
    return counts

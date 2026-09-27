from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from importlib import resources

import psycopg
from psycopg import sql

from .pipeline import LoadData
from .review_design import REF_TABLES, REVIEW_FIELDS
from .tickets import TICKET_COLUMNS

log = logging.getLogger(__name__)

TABLES = (
    "jira_requests",
    "ref_categories",
    "ref_score_anchors",
    "ref_agent_archetypes",
    "ref_evidence_basis",
    "ref_knowledge_deflection_anchors",
)

_FIELD_COLUMNS = {"exclude": "is_excluded"}


def load(
    conn: psycopg.Connection, data: LoadData, analyst_user: str, analyst_password: str
) -> dict[str, int]:
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(_script("schema.sql"))
        _copy(
            cur,
            "jira_requests",
            TICKET_COLUMNS,
            ([row[column] for column in TICKET_COLUMNS] for row in data.tickets),
        )
        for table in REF_TABLES:
            records = data.review_design.get(table.name, [])
            _copy(
                cur,
                table.name,
                table.columns,
                ([record[column] for column in table.columns] for record in records),
            )
        cur.execute(_script("views.sql"))
        _comment_columns(cur, data.review_design.get(REVIEW_FIELDS.name, []))
        _grant_read_only(cur, analyst_user, analyst_password)
        return _row_counts(cur)


def _script(name: str) -> str:
    return (resources.files("jsm_loader") / "sql" / name).read_text(encoding="utf-8")


def _copy(
    cur: psycopg.Cursor,
    table: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[object]],
) -> None:
    statement = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, columns))
    )
    with cur.copy(statement) as copy:
        for row in rows:
            copy.write_row(row)


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
            sql.SQL("COMMENT ON COLUMN jira_requests.{} IS {}").format(
                sql.Identifier(column), sql.Literal(record["notes"])
            )
        )


def _grant_read_only(cur: psycopg.Cursor, user: str, password: str) -> None:
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (user,))
    verb = "ALTER" if cur.fetchone() else "CREATE"
    role = sql.Identifier(user)
    cur.execute(
        sql.SQL("{} ROLE {} LOGIN PASSWORD {}").format(sql.SQL(verb), role, sql.Literal(password))
    )
    cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
    cur.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(role))


def _row_counts(cur: psycopg.Cursor) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in TABLES:
        cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table)))
        (counts[table],) = cur.fetchone()
    return counts

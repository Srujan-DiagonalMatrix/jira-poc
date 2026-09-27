from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from . import cells
from .sources import SourceError, open_workbook

log = logging.getLogger(__name__)

SHEET = "Jira Requests"

TICKET_COLUMNS = (
    "issue_type",
    "key",
    "summary",
    "description",
    "request_type",
    "request_topic",
    "assignee",
    "status",
    "created",
    "reporter",
    "synced_to_jira",
    "resolved",
    "linked_issues",
    "comment_summary",
    "priority",
    "severity",
    "is_excluded",
    "exclude_reason",
    "primary_category",
    "secondary_category",
    "sub_type",
    "is_batch",
    "is_project_work",
    "clarity",
    "complexity",
    "knowledge_deflection",
    "automation_logic",
    "action_class",
    "approval_required",
    "agent_archetype",
    "confidence",
    "rationale",
    "data_domain",
    "reversibility",
    "evidence_basis",
)

_RENAMES = {
    "Key (PK)": "key",
    "Key": "key",
    "What can we help you with?": "request_topic",
    "Sync to Jira": "synced_to_jira",
    "commentSummary": "comment_summary",
}
_CALCULATED = {"Duration (Days)"}
_FIELDS = tuple(
    "exclude" if column == "is_excluded" else column
    for column in TICKET_COLUMNS
    if column != "exclude_reason"
)
_REQUIRED = ("issue_type", "status", "created")
_CONVERTERS: dict[str, Callable[[object], object]] = {
    "synced_to_jira": cells.synced,
    "created": cells.utc,
    "resolved": cells.utc,
    "comment_summary": cells.comment_summary,
    "is_batch": cells.yes_no,
    "is_project_work": cells.yes_no,
    "clarity": cells.score,
    "complexity": cells.score,
    "knowledge_deflection": cells.score,
    "automation_logic": cells.score,
}


@dataclass(frozen=True)
class _Column:
    index: int
    header: str


def read_tickets(path: Path) -> list[dict[str, object]]:
    with open_workbook(path) as workbook:
        if SHEET not in workbook.sheetnames:
            raise SourceError(f"{path.name}: there is no '{SHEET}' sheet")
        sheet = workbook[SHEET]
        sheet.reset_dimensions()
        rows = sheet.iter_rows(values_only=True)
        columns = _map_headers(path, next(rows, ()))
        tickets = _read_rows(path, columns, rows)
    log.info("%s: read %d tickets", path.name, len(tickets))
    return tickets


def _field(header: str) -> str:
    return _RENAMES.get(header) or re.sub(r"[^0-9a-z]+", "_", header.lower()).strip("_")


def _map_headers(path: Path, header_row: Sequence[object]) -> dict[str, _Column]:
    columns: dict[str, _Column] = {}
    for index, value in enumerate(header_row):
        header = cells.text(value)
        if header is None or header in _CALCULATED:
            continue
        field = _field(header)
        if field not in _FIELDS:
            log.warning("%s: ignoring unknown column '%s' in sheet '%s'", path.name, header, SHEET)
            continue
        if field in columns:
            raise SourceError(
                f"{path.name}: sheet '{SHEET}' has two columns for {field}: "
                f"'{columns[field].header}' and '{header}'"
            )
        columns[field] = _Column(index, header)
    missing = [field for field in _FIELDS if field not in columns]
    if missing:
        raise SourceError(f"{path.name}: sheet '{SHEET}' is missing columns: {', '.join(missing)}")
    return columns


def _read_rows(
    path: Path, columns: dict[str, _Column], rows: Iterable[Sequence[object]]
) -> list[dict[str, object]]:
    tickets: list[dict[str, object]] = []
    first_row_of: dict[str, int] = {}
    for row_no, row in enumerate(rows, start=2):
        if all(cells.text(value) is None for value in row):
            continue
        where = f"{path.name}, sheet '{SHEET}', row {row_no}"
        values = {field: cells.value_at(row, column.index) for field, column in columns.items()}
        key = cells.text(values["key"])
        if key is None:
            raise SourceError(f"{where}: the key is empty")
        if key in first_row_of:
            raise SourceError(f"{where}: key {key} is also in row {first_row_of[key]}")
        first_row_of[key] = row_no
        ticket = _convert(f"{where} (key {key})", columns, values)
        for field in _REQUIRED:
            if ticket[field] is None:
                raise SourceError(f"{where} (key {key}): {field} is empty")
        tickets.append(ticket)
    return tickets


def _convert(
    where: str, columns: dict[str, _Column], values: dict[str, object]
) -> dict[str, object]:
    ticket: dict[str, object] = {}
    for field, value in values.items():
        try:
            if field == "exclude":
                ticket["is_excluded"], ticket["exclude_reason"] = cells.exclusion(value)
            else:
                ticket[field] = _CONVERTERS.get(field, cells.text)(value)
        except ValueError as exc:
            raise SourceError(f"{where}, column '{columns[field].header}': {exc}") from exc
    return {column: ticket[column] for column in TICKET_COLUMNS}

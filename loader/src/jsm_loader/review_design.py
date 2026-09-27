from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from . import cells
from .sources import SourceError, open_workbook

log = logging.getLogger(__name__)

SHEET = "Request Review Design"

_MARKER = re.compile(r"^(REVIEW SCHEMA|TABLE [A-Z])$")


@dataclass(frozen=True)
class RefTable:
    name: str
    marker: str
    headers: dict[str, str]

    @property
    def columns(self) -> tuple[str, ...]:
        return tuple(self.headers.values())


REVIEW_FIELDS = RefTable("review_fields", "REVIEW SCHEMA", {"Field": "field", "Notes": "notes"})

REF_TABLES = (
    RefTable(
        "ref_categories",
        "TABLE A",
        {"#": "category_no", "Category": "category", "Detail": "detail"},
    ),
    RefTable(
        "ref_score_anchors",
        "TABLE B",
        {
            "Score": "score",
            "General Logic": "general_logic",
            "Anchor (Clarity Example)": "clarity_anchor",
        },
    ),
    RefTable(
        "ref_agent_archetypes",
        "TABLE C",
        {
            "#": "archetype_no",
            "Archetype": "archetype",
            "Handles": "handles",
            "Autonomy": "autonomy",
            "Blocked by": "blocked_by",
        },
    ),
    RefTable(
        "ref_evidence_basis",
        "TABLE D",
        {"Value": "value", "Definition": "definition"},
    ),
    # TABLE E sits beside TABLE B in the sheet and shares its header row and Score column.
    RefTable(
        "ref_knowledge_deflection_anchors",
        "TABLE B",
        {"Score": "score", "Anchor (knowledge_deflection)": "knowledge_deflection_anchor"},
    ),
)

_BLOCKS = (REVIEW_FIELDS, *REF_TABLES)

_CONVERTERS: dict[str, Callable[[object], object]] = {
    "category_no": cells.whole_number,
    "score": cells.score,
    "archetype_no": cells.whole_number,
}

Row = Sequence[object]


def read_review_design(path: Path) -> dict[str, list[dict[str, object]]]:
    with open_workbook(path) as workbook:
        if SHEET not in workbook.sheetnames:
            log.warning(
                "%s: there is no '%s' sheet, so the ref_* tables stay empty", path.name, SHEET
            )
            return {table.name: [] for table in _BLOCKS}
        sheet = workbook[SHEET]
        sheet.reset_dimensions()
        rows = [tuple(row) for row in sheet.iter_rows(values_only=True)]
    markers = _find_markers(path, rows)
    tables = {table.name: _read_table(path, table, rows, markers) for table in _BLOCKS}
    log.info(
        "%s: read %s",
        path.name,
        ", ".join(f"{len(records)} {name}" for name, records in tables.items()),
    )
    return tables


def _marker(row: Row) -> str | None:
    label = cells.text(cells.value_at(row, 0))
    return label if label is not None and _MARKER.match(label) else None


def _find_markers(path: Path, rows: Sequence[Row]) -> dict[str, int]:
    markers: dict[str, int] = {}
    for index, row in enumerate(rows):
        label = _marker(row)
        if label is None:
            continue
        if label in markers:
            raise SourceError(
                f"{path.name}, sheet '{SHEET}': '{label}' is in rows {markers[label] + 1} "
                f"and {index + 1}"
            )
        markers[label] = index
    return markers


def _read_table(
    path: Path, table: RefTable, rows: Sequence[Row], markers: dict[str, int]
) -> list[dict[str, object]]:
    where = f"{path.name}, sheet '{SHEET}'"
    start = markers.get(table.marker)
    if start is None:
        raise SourceError(f"{where}: there is no '{table.marker}' block")
    header_row = rows[start + 1] if start + 1 < len(rows) else ()
    positions: dict[str, int] = {}
    for index, value in enumerate(header_row):
        header = cells.text(value)
        if header is not None:
            positions.setdefault(header, index)
    missing = [header for header in table.headers if header not in positions]
    if missing:
        raise SourceError(
            f"{where}: block '{table.marker}' is missing columns: {', '.join(missing)}"
        )
    key_header = next(iter(table.headers))
    records: list[dict[str, object]] = []
    for index in range(start + 2, len(rows)):
        row = rows[index]
        if _marker(row) is not None or all(cells.text(value) is None for value in row):
            break
        record: dict[str, object] = {}
        for header, column in table.headers.items():
            value = cells.value_at(row, positions[header])
            try:
                record[column] = _CONVERTERS.get(column, cells.text)(value)
            except ValueError as exc:
                raise SourceError(f"{where}, row {index + 1}, column '{header}': {exc}") from exc
        if record[table.headers[key_header]] is None:
            raise SourceError(f"{where}, row {index + 1}: '{key_header}' is empty")
        records.append(record)
    return records

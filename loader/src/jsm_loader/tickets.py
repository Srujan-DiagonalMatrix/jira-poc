from __future__ import annotations

import logging
import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from . import cells
from .review_design import ReviewDesign
from .sources import SourceError, open_workbook

log = logging.getLogger(__name__)

SHEET = "Jira Requests"

TICKET_COLUMNS = (
    "key",
    "issue_type",
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
    "duration_days",
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

ALLOWED_VALUES = {
    "action_class": ("read-only", "standard write", "privileged write", "config change"),
    "approval_required": ("none", "manager", "segregation-of-duties"),
    "confidence": ("low", "medium", "high"),
    "data_domain": (
        "permissions",
        "customer record",
        "billing record",
        "configuration",
        "reporting object",
        "none",
    ),
    "reversibility": ("easy", "hard", "irreversible"),
}

_RENAMES = {
    "Key (PK)": "key",
    "Key": "key",
    "What can we help you with?": "request_topic",
    "Sync to Jira": "synced_to_jira",
    "commentSummary": "comment_summary",
}
_FIELDS = tuple(
    "exclude" if column == "is_excluded" else column
    for column in TICKET_COLUMNS
    if column != "exclude_reason"
)
_REQUIRED = ("key", "issue_type", "status", "created")
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
NOTE_ARCHETYPE_NONE = "agent_archetype 'none' stored as empty"
NOTE_DURATION_KEPT = "durations kept from the workbook"
NOTE_DURATION_CALCULATED = "durations calculated from created and resolved"
NOTE_DURATION_EMPTY = "durations left empty because the ticket is not resolved"
NOTE_DURATION_NOT_A_NUMBER = "durations in the workbook that are not a number"
NOTE_DURATION_NEGATIVE = "negative durations in the workbook, recalculated"
NOTE_DURATION_FOR_UNRESOLVED = "durations in the workbook for unresolved tickets, left empty"
NOTES = (
    NOTE_ARCHETYPE_NONE,
    NOTE_DURATION_KEPT,
    NOTE_DURATION_CALCULATED,
    NOTE_DURATION_EMPTY,
    NOTE_DURATION_NOT_A_NUMBER,
    NOTE_DURATION_NEGATIVE,
    NOTE_DURATION_FOR_UNRESOLVED,
)

_SCORE_FIELDS = ("clarity", "complexity", "automation_logic")
_DAY = Decimal(86400)
_FOUR_PLACES = Decimal("0.0001")


@dataclass(frozen=True)
class SourceRow:
    number: int
    values: dict[str, object]


@dataclass(frozen=True)
class TicketSheet:
    columns: dict[str, str]
    rows: list[SourceRow]


@dataclass(frozen=True)
class References:
    categories: frozenset[str]
    scores: frozenset[int]
    deflection_scores: frozenset[int]
    archetypes: frozenset[str]
    evidence: frozenset[str]

    @classmethod
    def from_design(cls, design: ReviewDesign) -> References:
        def values(table: str, column: str) -> frozenset:
            return frozenset(record[column] for record in design.tables.get(table, []))

        return cls(
            categories=values("ref_categories", "category"),
            scores=values("ref_score_anchors", "score"),
            deflection_scores=values("ref_knowledge_deflection_anchors", "score"),
            archetypes=values("ref_agent_archetypes", "archetype"),
            evidence=values("ref_evidence_basis", "value"),
        )


@dataclass
class Staging:
    rows: list[dict[str, object]] = field(default_factory=list)
    not_staged: list[tuple[int, str]] = field(default_factory=list)
    problems: Counter[str] = field(default_factory=Counter)
    notes: Counter[str] = field(default_factory=Counter)

    @property
    def quarantined(self) -> list[dict[str, object]]:
        return [row for row in self.rows if row["validation_status"] == "QUARANTINED"]


def read_ticket_sheet(path: Path) -> TicketSheet:
    with open_workbook(path) as workbook:
        if SHEET not in workbook.sheetnames:
            raise SourceError(f"{path.name}: there is no '{SHEET}' sheet")
        sheet = workbook[SHEET]
        sheet.reset_dimensions()
        rows = sheet.iter_rows(values_only=True)
        headers = [cells.text(value) for value in next(rows, ())]
        columns = _map_headers(path, headers)
        source_rows = _read_rows(headers, rows)
    log.info("%s: read %d ticket rows", path.name, len(source_rows))
    return TicketSheet(columns, source_rows)


def stage_tickets(sheet: TicketSheet, refs: References) -> Staging:
    staging = Staging()
    for row in sheet.rows:
        _stage_row(sheet.columns, row, refs, staging)
    _quarantine_duplicate_keys(staging)
    return staging


def _field(header: str) -> str:
    return _RENAMES.get(header) or re.sub(r"[^0-9a-z]+", "_", header.lower()).strip("_")


def _map_headers(path: Path, headers: Sequence[str | None]) -> dict[str, str]:
    columns: dict[str, str] = {}
    for header in headers:
        if header is None:
            continue
        field_name = _field(header)
        if field_name not in _FIELDS:
            log.warning("%s: ignoring unknown column '%s' in sheet '%s'", path.name, header, SHEET)
            continue
        if field_name in columns:
            raise SourceError(
                f"{path.name}: sheet '{SHEET}' has two columns for {field_name}: "
                f"'{columns[field_name]}' and '{header}'"
            )
        columns[field_name] = header
    missing = [field_name for field_name in _FIELDS if field_name not in columns]
    if missing:
        raise SourceError(f"{path.name}: sheet '{SHEET}' is missing columns: {', '.join(missing)}")
    return columns


def _read_rows(headers: Sequence[str | None], rows: Iterable[Sequence[object]]) -> list[SourceRow]:
    source_rows: list[SourceRow] = []
    for row_no, row in enumerate(rows, start=2):
        if all(cells.text(value) is None for value in row):
            continue
        values = {
            header: cells.value_at(row, index)
            for index, header in enumerate(headers)
            if header is not None
        }
        source_rows.append(SourceRow(row_no, values))
    return source_rows


def _stage_row(
    columns: Mapping[str, str], row: SourceRow, refs: References, staging: Staging
) -> None:
    ticket: dict[str, object] = {}
    problems: list[str] = []

    def problem(kind: str, message: str) -> None:
        problems.append(message)
        staging.problems[kind] += 1

    for field_name, header in columns.items():
        if field_name == "duration_days":
            continue
        value = row.values.get(header)
        try:
            if field_name == "exclude":
                ticket["is_excluded"], ticket["exclude_reason"] = cells.exclusion(value)
            else:
                ticket[field_name] = _CONVERTERS.get(field_name, cells.text)(value)
        except ValueError as exc:
            if field_name == "exclude":
                ticket["is_excluded"], ticket["exclude_reason"] = False, None
            else:
                ticket[field_name] = None
            problem("conversion", f"column '{header}': {exc}")

    missing = [field_name for field_name in _REQUIRED if ticket.get(field_name) is None]
    if missing:
        if "key" in missing:
            staging.problems["missing key"] += 1
        if any(field_name != "key" for field_name in missing):
            staging.problems["missing required"] += 1
        reason = f"{', '.join(missing)} missing or unreadable"
        staging.not_staged.append((row.number, "; ".join([reason, *problems])))
        return

    if ticket["agent_archetype"] == "none":
        ticket["agent_archetype"] = None
        staging.notes[NOTE_ARCHETYPE_NONE] += 1

    ticket["duration_days"] = _duration(row.values.get(columns["duration_days"]), ticket, staging)
    if ticket["duration_days"] is not None and ticket["duration_days"] < 0:
        problem("duration", "resolved is before created")

    _validate(ticket, refs, problem)
    staging.rows.append(
        {
            "source_row_number": row.number,
            **{column: ticket[column] for column in TICKET_COLUMNS},
            "validation_status": "QUARANTINED" if problems else "VALID",
            "validation_message": "; ".join(problems) or None,
        }
    )


def _duration(
    supplied_value: object, ticket: dict[str, object], staging: Staging
) -> Decimal | None:
    try:
        supplied = cells.number(supplied_value)
    except ValueError:
        supplied = None
        staging.notes[NOTE_DURATION_NOT_A_NUMBER] += 1
    resolved, created = ticket["resolved"], ticket["created"]
    if resolved is None:
        if supplied is not None:
            staging.notes[NOTE_DURATION_FOR_UNRESOLVED] += 1
        staging.notes[NOTE_DURATION_EMPTY] += 1
        return None
    if supplied is not None and supplied >= 0:
        staging.notes[NOTE_DURATION_KEPT] += 1
        return supplied
    if supplied is not None:
        staging.notes[NOTE_DURATION_NEGATIVE] += 1
    staging.notes[NOTE_DURATION_CALCULATED] += 1
    seconds = Decimal(str((resolved - created).total_seconds()))
    return (seconds / _DAY).quantize(_FOUR_PLACES, rounding=ROUND_HALF_UP)


def _validate(
    ticket: dict[str, object], refs: References, problem: Callable[[str, str], None]
) -> None:
    if not ticket["is_excluded"] and ticket["exclude_reason"] is not None:
        problem("exclusion", "exclude is N but has a reason; only excluded tickets can have one")
    category = ticket["primary_category"]
    if category is None and not ticket["is_excluded"]:
        problem("primary_category", "primary_category is missing")
    elif category is not None and category not in refs.categories:
        problem("primary_category", f"primary_category {category!r} is not in ref_categories")
    secondary = ticket["secondary_category"]
    if secondary is not None and secondary not in refs.categories:
        problem("secondary_category", f"secondary_category {secondary!r} is not in ref_categories")
    for score_field in _SCORE_FIELDS:
        score = ticket[score_field]
        if score is not None and score not in refs.scores:
            problem("score", f"{score_field} {score} is not in ref_score_anchors")
    deflection = ticket["knowledge_deflection"]
    if deflection is not None and deflection not in refs.deflection_scores:
        problem(
            "knowledge_deflection",
            f"knowledge_deflection {deflection} is not in ref_knowledge_deflection_anchors",
        )
    archetype = ticket["agent_archetype"]
    if archetype is not None and archetype not in refs.archetypes:
        problem("agent_archetype", f"agent_archetype {archetype!r} is not in ref_agent_archetypes")
    evidence = ticket["evidence_basis"]
    if evidence is not None and evidence not in refs.evidence:
        problem("evidence_basis", f"evidence_basis {evidence!r} is not in ref_evidence_basis")
    for column, allowed in ALLOWED_VALUES.items():
        value = ticket[column]
        if value is not None and value not in allowed:
            problem("allowed value", f"{column} {value!r} is not an allowed value")


def _quarantine_duplicate_keys(staging: Staging) -> None:
    rows_by_key: dict[object, list[dict[str, object]]] = {}
    for row in staging.rows:
        rows_by_key.setdefault(row["key"], []).append(row)
    for key, rows in rows_by_key.items():
        if len(rows) < 2:
            continue
        numbers = ", ".join(str(row["source_row_number"]) for row in rows)
        for row in rows:
            message = f"key {key} is in rows {numbers}"
            existing = row["validation_message"]
            row["validation_message"] = f"{existing}; {message}" if existing else message
            row["validation_status"] = "QUARANTINED"
            staging.problems["duplicate key"] += 1

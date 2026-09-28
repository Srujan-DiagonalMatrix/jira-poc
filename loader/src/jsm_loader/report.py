from __future__ import annotations

import logging
from collections import Counter

from .pipeline import LoadData
from .tickets import NOTES

EXPECTED_SOURCE_ROWS = 5344
EXPECTED_REF_ROWS = {"ref_categories": 9, "ref_agent_archetypes": 5, "ref_evidence_basis": 4}
SCORE_TABLES = ("ref_score_anchors", "ref_knowledge_deflection_anchors")
_EXAMPLES = 10

_PROBLEMS = (
    ("duplicate key", "rows with a duplicate Jira key"),
    ("conversion", "unreadable dates, Y/N flags, Sync to Jira, exclusion or score values"),
    ("exclusion", "tickets that aren't excluded but have an exclusion reason"),
    ("duration", "tickets resolved before they were created"),
    ("primary_category", "invalid or missing primary categories"),
    ("secondary_category", "invalid secondary categories"),
    ("score", "invalid clarity, complexity or automation_logic scores"),
    ("knowledge_deflection", "invalid knowledge_deflection scores"),
    ("agent_archetype", "invalid agent archetypes"),
    ("evidence_basis", "invalid evidence_basis values"),
    (
        "allowed value",
        "action_class, approval_required, confidence, data_domain or reversibility values "
        "not in the review schema",
    ),
)

Line = tuple[int, str]


def validation_report(data: LoadData, ref_keys: dict[str, list[object]]) -> list[Line]:
    staging = data.staging
    lines: list[Line] = []

    def add(message: str, problem: bool = False) -> None:
        lines.append((logging.WARNING if problem else logging.INFO, message))

    source_rows = len(data.tickets.rows)
    add(
        f"source rows: {source_rows} (expected {EXPECTED_SOURCE_ROWS})",
        source_rows != EXPECTED_SOURCE_ROWS,
    )
    missing_keys = staging.problems["missing key"]
    add(f"rows with a missing or unreadable Jira key, not staged: {missing_keys}", missing_keys > 0)
    missing_required = staging.problems["missing required"]
    add(
        f"rows with a missing or unreadable issue_type, status or created, not staged: "
        f"{missing_required}",
        missing_required > 0,
    )
    for row_number, reason in staging.not_staged[:_EXAMPLES]:
        add(f"  row {row_number}: {reason}", True)
    for kind, label in _PROBLEMS:
        add(f"{label}: {staging.problems[kind]}", staging.problems[kind] > 0)
    for note in NOTES:
        add(f"{note}: {staging.notes[note]}")
    for table, expected in EXPECTED_REF_ROWS.items():
        count = len(ref_keys.get(table, []))
        add(f"{table}: {count} rows (expected {expected})", count != expected)
    for table in SCORE_TABLES:
        scores = sorted(ref_keys.get(table, []))
        add(f"{table}: scores {scores} (expected [1, 2, 3, 4, 5])", scores != [1, 2, 3, 4, 5])
    quarantined = staging.quarantined
    add(f"quarantined rows: {len(quarantined)} of {len(staging.rows)} staged", bool(quarantined))
    reasons = Counter(
        reason for row in quarantined for reason in str(row["validation_message"]).split("; ")
    )
    for reason, count in reasons.most_common(_EXAMPLES):
        add(f"  {count} x {reason}", True)
    return lines

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .review_design import ReviewDesign, read_review_design
from .tickets import References, Staging, TicketSheet, read_ticket_sheet, stage_tickets


@dataclass(frozen=True)
class LoadData:
    source_file: str
    tickets: TicketSheet
    review_design: ReviewDesign
    staging: Staging


def collect(scored: Path) -> LoadData:
    tickets = read_ticket_sheet(scored)
    review_design = read_review_design(scored)
    staging = stage_tickets(tickets, References.from_design(review_design))
    return LoadData(scored.name, tickets, review_design, staging)

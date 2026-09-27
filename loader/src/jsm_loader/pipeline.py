from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .review_design import read_review_design
from .tickets import read_tickets


@dataclass(frozen=True)
class LoadData:
    tickets: list[dict[str, object]]
    review_design: dict[str, list[dict[str, object]]]


def collect(scored: Path) -> LoadData:
    return LoadData(tickets=read_tickets(scored), review_design=read_review_design(scored))

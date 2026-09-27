from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from openpyxl import Workbook, load_workbook

log = logging.getLogger(__name__)

_SCORED_SHEET = "Jira Requests"
_SKIPPED_PREFIXES = (".", "~$")


class SourceError(Exception):
    pass


@contextmanager
def open_workbook(path: Path) -> Iterator[Workbook]:
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise SourceError(f"{path.name}: can't open this Excel file ({exc})") from exc
    try:
        yield workbook
    finally:
        workbook.close()


def discover(source_dir: Path) -> Path:
    if not source_dir.is_dir():
        raise SourceError(f"source folder not found: {source_dir}")
    found: list[Path] = []
    for path in sorted(source_dir.iterdir()):
        if path.name.startswith(_SKIPPED_PREFIXES) or not path.is_file():
            continue
        if _is_scored(path):
            found.append(path)
        else:
            log.warning("ignoring %s: it is not a scored workbook", path.name)
    if len(found) > 1:
        names = ", ".join(path.name for path in found)
        raise SourceError(f"found more than one scored workbook in {source_dir}: {names}")
    if not found:
        raise SourceError(
            f"no scored workbook (an .xlsx file with a '{_SCORED_SHEET}' sheet) in {source_dir}"
        )
    log.info("found scored workbook: %s", found[0].name)
    return found[0]


def _is_scored(path: Path) -> bool:
    if path.suffix.lower() != ".xlsx":
        return False
    with open_workbook(path) as workbook:
        return _SCORED_SHEET in workbook.sheetnames

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime, timezone

_EXCLUSION = re.compile(r"^(?P<flag>[YN])\b\s*(?:[—–-]\s*(?P<reason>.+))?$", re.DOTALL)
_NO_FIELD = "[no field found]"


def value_at(row: Sequence[object], index: int) -> object:
    return row[index] if index < len(row) else None


def text(value: object) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def yes_no(value: object) -> bool | None:
    flag = text(value)
    if flag is None:
        return None
    if flag == "Y":
        return True
    if flag == "N":
        return False
    raise ValueError(f"{value!r} is not Y or N")


def whole_number(value: object) -> int | None:
    if _is_blank(value):
        return None
    if isinstance(value, bool):
        raise ValueError(f"{value!r} is not a whole number")
    if isinstance(value, int):
        return value
    try:
        number = float(value.strip() if isinstance(value, str) else value)
    except (TypeError, ValueError):
        raise ValueError(f"{value!r} is not a whole number") from None
    if not number.is_integer():
        raise ValueError(f"{value!r} is not a whole number")
    return int(number)


def score(value: object) -> int | None:
    message = f"{value!r} is not a whole number from 1 to 5"
    try:
        number = whole_number(value)
    except ValueError:
        raise ValueError(message) from None
    if number is not None and not 1 <= number <= 5:
        raise ValueError(message)
    return number


def utc(value: object) -> datetime | None:
    if _is_blank(value):
        return None
    if not isinstance(value, datetime):
        raise ValueError(f"{value!r} is not a date and time")
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def exclusion(value: object) -> tuple[bool, str | None]:
    flag = text(value)
    if flag is None:
        return False, None
    match = _EXCLUSION.match(flag)
    if match is None:
        raise ValueError(f"{value!r} is not N, Y, or Y followed by a dash and a reason")
    return match.group("flag") == "Y", text(match.group("reason"))


def synced(value: object) -> bool:
    state = text(value)
    if state is None:
        return False
    if state == "Synced":
        return True
    raise ValueError(f"{value!r} is not 'Synced' or blank")


def comment_summary(value: object) -> str | None:
    summary = text(value)
    return None if summary == _NO_FIELD else summary


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())

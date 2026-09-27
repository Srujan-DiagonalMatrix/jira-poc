from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    database_url: str
    source_dir: Path
    analyst_user: str
    analyst_password: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        password = env.get("ANALYST_PASSWORD", "")
        if not password:
            raise ConfigError("ANALYST_PASSWORD is not set")
        return cls(
            database_url=env.get("DATABASE_URL", ""),
            source_dir=Path(env.get("SOURCE_DIR") or "/data/source"),
            analyst_user=env.get("ANALYST_USER") or "analyst",
            analyst_password=password,
        )

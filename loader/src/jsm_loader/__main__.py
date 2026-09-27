from __future__ import annotations

import logging
import sys

import psycopg

from .config import ConfigError, Settings
from .db import load
from .pipeline import collect
from .sources import SourceError, discover

log = logging.getLogger("jsm_loader")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.captureWarnings(True)
    try:
        settings = Settings.from_env()
        data = collect(discover(settings.source_dir))
        log.info("loading into PostgreSQL")
        with psycopg.connect(settings.database_url) as conn:
            counts = load(conn, data, settings.analyst_user, settings.analyst_password)
    except (ConfigError, SourceError, psycopg.Error) as exc:
        log.error("%s", exc)
        log.error("nothing was changed in the database")
        return 1
    for table, count in counts.items():
        log.info("%s: %d rows", table, count)
    log.info("load complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())

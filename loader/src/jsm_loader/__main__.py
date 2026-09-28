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
            result = load(conn, data, settings.analyst_user, settings.analyst_password)
    except (ConfigError, SourceError, psycopg.Error) as exc:
        log.error("%s", exc)
        log.error("nothing was changed in the database")
        return 1
    for table, count in result.counts.items():
        log.info("jira_ai.%s: %d rows", table, count)
    if result.quarantined:
        log.warning(
            "%d rows were quarantined and not loaded; see jira_ai.stg_jira_requests for batch %s",
            result.quarantined,
            result.batch_id,
        )
    log.info("load complete (batch %s)", result.batch_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())

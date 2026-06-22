import logging

from sqlalchemy import text

from database.database import Base, engine
from database import models  # noqa: F401 — side effect: registers all models

logger = logging.getLogger(__name__)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def _run_migrations() -> None:
    """
    Idempotent column additions for existing deployments.
    Each ALTER is wrapped in a column-existence check so it's safe to re-run.
    """
    migrations = [
        (
            "jobs",
            "progress",
            "ALTER TABLE jobs ADD COLUMN progress INTEGER NOT NULL DEFAULT 0",
        ),
        (
            "transcripts",
            "full_text_vector",
            "ALTER TABLE transcripts ADD COLUMN full_text_vector tsvector",
        ),
        (
            "transcripts",
            "duration_sec",
            "ALTER TABLE transcripts ADD COLUMN duration_sec FLOAT",
        ),
        (
            "transcripts",
            "language",
            "ALTER TABLE transcripts ADD COLUMN language VARCHAR(10)",
        ),
    ]

    with engine.connect() as conn:
        for table, column, ddl in migrations:
            exists = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = :t AND column_name = :c"
                ),
                {"t": table, "c": column},
            ).fetchone()

            if exists is None:
                conn.execute(text(ddl))
                conn.commit()
                logger.info("Migration applied: added %s.%s", table, column)
            else:
                logger.debug("Migration skipped: %s.%s already exists", table, column)

        # GIN index on tsvector — idempotent via IF NOT EXISTS
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_transcripts_fts "
            "ON transcripts USING GIN (full_text_vector)"
        ))
        conn.commit()

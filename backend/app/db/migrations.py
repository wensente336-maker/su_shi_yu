"""Small, idempotent PostgreSQL migrations for installations created before Alembic.

Keep each migration safe to run on every startup. New migrations must have a new
version identifier and be appended to ``MIGRATIONS``.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session


def run_migrations(db: Session) -> None:
    db.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version varchar(100) PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"))
    applied = set(db.scalars(text("SELECT version FROM schema_migrations")).all())
    for version, statements in MIGRATIONS:
        if version in applied:
            continue
        for statement in statements:
            db.execute(text(statement))
        db.execute(text("INSERT INTO schema_migrations (version) VALUES (:version)"), {"version": version})
        db.commit()


MIGRATIONS = [
    (
        "20260827_submission_subject_index",
        [
            "ALTER TABLE form_submissions ADD COLUMN IF NOT EXISTS subject_key varchar(180)",
            """
            UPDATE form_submissions AS submission
            SET subject_key = CASE
                WHEN schema.code = 'sales-weekly-v1' THEN 'sales:' || lower(trim(coalesce(submission.values->>'sales_person', '')))
                ELSE 'employee:' || submission.employee_id::text
            END
            FROM form_schemas AS schema
            WHERE schema.id = submission.schema_id AND submission.subject_key IS NULL
            """,
            "ALTER TABLE form_submissions ALTER COLUMN subject_key SET NOT NULL",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_submission_subject ON form_submissions (schema_id, reporting_week_id, subject_key)",
        ],
    ),
]

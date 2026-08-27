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
    (
        "20260827_hermes_agent_jobs",
        [
            """
            CREATE TABLE IF NOT EXISTS hermes_analysis_jobs (
                id serial PRIMARY KEY,
                reporting_week_id integer NOT NULL REFERENCES reporting_weeks(id),
                idempotency_key varchar(120) NOT NULL UNIQUE,
                status varchar(20) NOT NULL DEFAULT 'queued',
                payload json NOT NULL DEFAULT '{}'::json,
                agent_id varchar(100),
                lease_token_hash varchar(64),
                lease_expires_at timestamptz,
                attempt_count integer NOT NULL DEFAULT 0,
                max_attempts integer NOT NULL DEFAULT 3,
                error_message text,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now(),
                completed_at timestamptz
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_hermes_analysis_jobs_status ON hermes_analysis_jobs (status)",
            "CREATE INDEX IF NOT EXISTS ix_hermes_analysis_jobs_lease_expires_at ON hermes_analysis_jobs (lease_expires_at)",
            """
            CREATE TABLE IF NOT EXISTS hermes_agent_nonces (
                id serial PRIMARY KEY,
                agent_id varchar(100) NOT NULL,
                nonce varchar(100) NOT NULL,
                expires_at timestamptz NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT uq_hermes_agent_nonce UNIQUE (agent_id, nonce)
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_hermes_agent_nonces_expires_at ON hermes_agent_nonces (expires_at)",
        ],
    ),
]

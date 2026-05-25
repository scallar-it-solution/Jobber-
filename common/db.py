from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - helpful before dependencies are installed.
    psycopg = None
    dict_row = None

from common.config import project_root


class Database:
    def __init__(self, url: str | None = None) -> None:
        self.url = url or os.getenv(
            "DATABASE_URL", "postgresql://autoapply:autoapply@localhost:5432/autoapply"
        )

    @contextmanager
    def connect(self):
        if psycopg is None:
            raise RuntimeError("Install dependencies first: pip install -r requirements.txt")
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            yield conn

    def init_schema(self, schema_path: str | Path | None = None) -> None:
        path = Path(schema_path) if schema_path else project_root() / "data" / "schema.sql"
        sql = path.read_text(encoding="utf-8")
        with self.connect() as conn:
            conn.execute(sql)

    def insert_job(self, job: dict[str, Any]) -> bool:
        columns = [
            "id",
            "platform",
            "title",
            "company",
            "location",
            "jd_text",
            "apply_url",
            "salary",
            "posted_at",
            "scraped_at",
            "status",
            "dedupe_hash",
        ]
        values = [job.get(column) for column in columns]
        placeholders = ", ".join(["%s"] * len(columns))
        assignments = ", ".join(
            [
                "location = EXCLUDED.location",
                "jd_text = COALESCE(NULLIF(EXCLUDED.jd_text, ''), jobs.jd_text)",
                "apply_url = COALESCE(NULLIF(EXCLUDED.apply_url, ''), jobs.apply_url)",
                "salary = COALESCE(NULLIF(EXCLUDED.salary, ''), jobs.salary)",
                "posted_at = COALESCE(EXCLUDED.posted_at, jobs.posted_at)",
                "scraped_at = EXCLUDED.scraped_at",
                "updated_at = NOW()",
            ]
        )
        query = f"""
            INSERT INTO jobs ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT (dedupe_hash) DO UPDATE SET {assignments}
            RETURNING xmax = 0 AS inserted
        """
        with self.connect() as conn:
            row = conn.execute(query, values).fetchone()
            return bool(row and row["inserted"])

    def fetch_job(self, job_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM jobs WHERE id = %s", (job_id,)).fetchone()

    def fetch_jobs_for_scoring(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM jobs
                WHERE status IN ('new', 'matched', 'queued')
                ORDER BY scraped_at DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
            return list(rows)

    def fetch_apply_queue(self, min_grade: str = "B", limit: int = 25) -> list[dict[str, Any]]:
        grade_rank = {"A": 4, "B": 3, "C": 2, "D": 1}
        min_rank = grade_rank.get(min_grade.upper(), 3)
        eligible = [grade for grade, rank in grade_rank.items() if rank >= min_rank]
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM jobs
                WHERE status = 'queued' AND match_grade = ANY(%s)
                ORDER BY composite_score DESC NULLS LAST, scraped_at DESC
                LIMIT %s
                """,
                (eligible, limit),
            ).fetchall()
            return list(rows)

    def count_applications_today(self, dry_run: bool = False) -> int:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM applications
                WHERE dry_run = %s AND applied_at::date = CURRENT_DATE
                """,
                (dry_run,),
            ).fetchone()
            return int(row["count"])

    def update_job_scores(
        self,
        job_id: str,
        ats_score: float,
        semantic_score: float,
        composite_score: float,
        match_grade: str,
        missing_keywords: Iterable[str],
        status: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET ats_score = %s,
                    semantic_score = %s,
                    composite_score = %s,
                    match_grade = %s,
                    missing_keywords = %s::jsonb,
                    status = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    round(ats_score, 2),
                    round(semantic_score, 2),
                    round(composite_score, 2),
                    match_grade,
                    json.dumps(list(missing_keywords)),
                    status,
                    job_id,
                ),
            )

    def update_job_status(
        self, job_id: str, status: str, error_reason: str | None = None, applied: bool = False
    ) -> None:
        applied_clause = ", applied_at = NOW()" if applied else ""
        with self.connect() as conn:
            conn.execute(
                f"""
                UPDATE jobs
                SET status = %s,
                    error_reason = %s,
                    updated_at = NOW()
                    {applied_clause}
                WHERE id = %s
                """,
                (status, error_reason, job_id),
            )

    def record_application(
        self,
        job_id: str,
        platform: str,
        status: str,
        dry_run: bool,
        response_payload: dict[str, Any] | None = None,
        error_reason: str | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO applications
                  (job_id, platform, status, dry_run, response_payload, error_reason)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                """,
                (
                    job_id,
                    platform,
                    status,
                    dry_run,
                    json.dumps(response_payload or {}),
                    error_reason,
                ),
            )

    def start_scraper_run(self, platform: str, role: str, location: str | None) -> str:
        with self.connect() as conn:
            row = conn.execute(
                """
                INSERT INTO scraper_runs (platform, role, location)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (platform, role, location),
            ).fetchone()
            return str(row["id"])

    def finish_scraper_run(
        self,
        run_id: str,
        jobs_found: int,
        jobs_inserted: int,
        status: str = "success",
        error_reason: str | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE scraper_runs
                SET finished_at = NOW(),
                    jobs_found = %s,
                    jobs_inserted = %s,
                    status = %s,
                    error_reason = %s
                WHERE id = %s
                """,
                (jobs_found, jobs_inserted, status, error_reason, run_id),
            )


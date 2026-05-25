from __future__ import annotations

from common.config import load_dotenv
from common.db import Database
from scraper.base import JobRecord


SAMPLE_JD = """
We are hiring a Data Engineer to build scalable data pipelines on AWS.
The role requires Python, SQL, Airflow, Spark, ETL design, data modeling,
and experience with cloud warehouses. Knowledge of MLOps, Docker, and
CI/CD is a plus.
"""


def main() -> None:
    load_dotenv()
    db = Database()
    db.init_schema()
    inserted = db.insert_job(
        JobRecord(
            platform="sample",
            title="Data Engineer",
            company="Sample Analytics",
            location="Noida",
            jd_text=SAMPLE_JD,
            apply_url="https://example.com/jobs/data-engineer",
        ).to_db_record()
    )
    print("Inserted sample job." if inserted else "Sample job already exists; refreshed it.")


if __name__ == "__main__":
    main()

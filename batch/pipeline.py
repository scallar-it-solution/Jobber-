from __future__ import annotations

from applier.run import run_applier
from common.config import load_dotenv, load_yaml
from common.db import Database
from matcher.batch_score import batch_score
from reports.generate import generate_daily_report
from scraper.run import run_scrapers


def init_db() -> None:
    load_dotenv()
    Database().init_schema()
    print("Database schema applied.")


def run_full_pipeline(scrape_limit: int | None = None, real_apply: bool = False) -> None:
    load_dotenv()
    filters = load_yaml("config/filters.yaml")
    init_db()
    run_scrapers(all_enabled=True, limit=scrape_limit)
    batch_score(min_grade=filters.get("min_match_grade", "B"))
    run_applier(min_grade=filters.get("min_match_grade", "B"), dry_run=not real_apply)
    generate_daily_report()


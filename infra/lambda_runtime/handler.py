from __future__ import annotations

import os
from typing import Any


def scraper_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    from common.config import load_dotenv
    from scraper.run import run_scrapers

    load_dotenv()
    platform = os.getenv("PLATFORM")
    run_scrapers(platform=platform, all_enabled=platform is None)
    return {"ok": True, "platform": platform or "all"}


def matcher_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    from common.config import load_dotenv
    from matcher.batch_score import batch_score

    load_dotenv()
    min_grade = os.getenv("MIN_MATCH_GRADE", "B")
    results = batch_score(min_grade=min_grade, limit=int(os.getenv("BATCH_LIMIT", "100")))
    return {"ok": True, "scored": len(results)}


def report_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    from common.config import load_dotenv
    from reports.generate import generate_daily_report

    load_dotenv()
    path = generate_daily_report()
    return {"ok": True, "report": str(path)}


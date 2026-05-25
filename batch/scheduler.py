from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from applier.run import run_applier
from common.config import load_dotenv, load_yaml
from matcher.batch_score import batch_score
from reports.generate import generate_daily_report
from scraper.run import run_scrapers


def start_scheduler() -> None:
    load_dotenv()
    filters = load_yaml("config/filters.yaml")
    min_grade = filters.get("min_match_grade", "B")
    scheduler = BlockingScheduler(timezone="Asia/Kolkata")

    scheduler.add_job(
        lambda: run_scrapers(all_enabled=True),
        CronTrigger(hour=7, minute=0, timezone="Asia/Kolkata"),
        id="morning_scrape",
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: batch_score(min_grade=min_grade),
        CronTrigger(hour=7, minute=30, timezone="Asia/Kolkata"),
        id="morning_match",
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: run_applier(min_grade=min_grade),
        CronTrigger(hour=8, minute=0, timezone="Asia/Kolkata"),
        id="morning_apply",
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: run_scrapers(all_enabled=True),
        CronTrigger(hour=18, minute=0, timezone="Asia/Kolkata"),
        id="evening_scrape",
        replace_existing=True,
    )
    scheduler.add_job(
        generate_daily_report,
        CronTrigger(hour=19, minute=0, timezone="Asia/Kolkata"),
        id="daily_report",
        replace_existing=True,
    )

    print("Scheduler started for Asia/Kolkata cron pipeline.")
    scheduler.start()


def main() -> None:
    start_scheduler()


if __name__ == "__main__":
    main()


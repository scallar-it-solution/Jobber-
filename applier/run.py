from __future__ import annotations

import argparse
import random
import time

from applier.base import ApplyResult
from applier.indeed_quick_apply import IndeedQuickApplyBot
from applier.linkedin_easy_apply import LinkedInEasyApplyBot
from common.config import bool_env, int_env, load_dotenv, load_yaml
from common.db import Database


BOTS = {
    "linkedin": LinkedInEasyApplyBot(),
    "indeed": IndeedQuickApplyBot(),
}


def run_applier(
    min_grade: str = "B",
    max_daily: int | None = None,
    dry_run: bool | None = None,
    sleep_between: bool = False,
) -> list[ApplyResult]:
    load_dotenv()
    filters = load_yaml("config/filters.yaml")
    profile = load_yaml("config/profile.yaml")
    database = Database()

    max_daily = max_daily or int_env("MAX_DAILY_APPLIES", int(filters.get("max_daily_applies", 25)))
    dry_run = bool_env("APPLIER_DRY_RUN", True) if dry_run is None else dry_run
    remaining = max_daily if dry_run else max(0, max_daily - database.count_applications_today(False))
    if remaining <= 0:
        print("Daily application limit reached.")
        return []

    jobs = database.fetch_apply_queue(min_grade=min_grade, limit=remaining)
    results: list[ApplyResult] = []
    for job in jobs:
        bot = BOTS.get(job["platform"])
        if not bot:
            result = ApplyResult("failed", f"No applier bot for platform: {job['platform']}")
        else:
            result = bot.apply(job, profile, dry_run=dry_run)

        database.record_application(
            str(job["id"]),
            job["platform"],
            result.status,
            dry_run,
            result.payload,
            None if result.status in {"applied", "dry_run"} else result.message,
        )

        if not dry_run:
            if result.status == "applied":
                database.update_job_status(str(job["id"]), "applied", applied=True)
            else:
                database.update_job_status(str(job["id"]), "failed", error_reason=result.message)

        print(f"{job['platform']} {job['company']} - {job['title']}: {result.status}")
        results.append(result)
        if sleep_between and not dry_run:
            time.sleep(random.randint(180, 480))

    return results


def main() -> None:
    load_dotenv()
    filters = load_yaml("config/filters.yaml")
    parser = argparse.ArgumentParser(description="Run the AutoApply application queue.")
    parser.add_argument("--min-grade", default=filters.get("min_match_grade", "B"))
    parser.add_argument("--max-daily", type=int)
    parser.add_argument("--real", action="store_true", help="Submit real applications.")
    parser.add_argument("--sleep-between", action="store_true")
    args = parser.parse_args()
    run_applier(
        min_grade=args.min_grade,
        max_daily=args.max_daily,
        dry_run=False if args.real else None,
        sleep_between=args.sleep_between,
    )


if __name__ == "__main__":
    main()


from __future__ import annotations

import argparse
import subprocess
import sys

from common.config import load_dotenv


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(prog="autoapply", description="AutoApply command center.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("init-db", help="Apply the PostgreSQL schema.")

    start = subcommands.add_parser("start", help="Run scrape, match, apply, and report.")
    start.add_argument("--scrape-limit", type=int)
    start.add_argument("--real-apply", action="store_true", help="Submit real applications.")

    scrape = subcommands.add_parser("scrape", help="Run scrapers.")
    scrape.add_argument("--platform", choices=["linkedin", "indeed", "naukri", "wellfound"])
    scrape.add_argument("--all-enabled", action="store_true")
    scrape.add_argument("--limit", type=int)

    phase1 = subcommands.add_parser(
        "phase1", help="Run first-phase Gurgaon/Noida job listing scrape."
    )
    phase1.add_argument("--platform", choices=["linkedin", "indeed", "naukri", "wellfound"])
    phase1.add_argument("--limit", type=int)
    phase1.add_argument("--preview", action="store_true", help="Print target matrix only.")

    match = subcommands.add_parser("match", help="Score jobs against the resume.")
    match.add_argument("--min-grade", default="B")
    match.add_argument("--limit", type=int, default=100)

    apply = subcommands.add_parser("apply", help="Run the application queue.")
    apply.add_argument("--min-grade", default="B")
    apply.add_argument("--max-daily", type=int)
    apply.add_argument("--real", action="store_true", help="Submit real applications.")
    apply.add_argument("--sleep-between", action="store_true")

    subcommands.add_parser("dashboard", help="Open the Go TUI dashboard.")
    subcommands.add_parser("report", help="Generate the daily report.")
    subcommands.add_parser("schedule", help="Run the local APScheduler cron pipeline.")

    args = parser.parse_args()

    if args.command == "init-db":
        from batch.pipeline import init_db

        init_db()
    elif args.command == "start":
        from batch.pipeline import run_full_pipeline

        run_full_pipeline(scrape_limit=args.scrape_limit, real_apply=args.real_apply)
    elif args.command == "scrape":
        from scraper.run import run_scrapers

        run_scrapers(platform=args.platform, all_enabled=args.all_enabled, limit=args.limit)
    elif args.command == "phase1":
        from scraper.run import preview_scrape_plan, run_scrapers

        if args.preview:
            preview_scrape_plan(
                platform=args.platform, all_enabled=args.platform is None, limit=args.limit
            )
            return
        run_scrapers(platform=args.platform, all_enabled=args.platform is None, limit=args.limit)
    elif args.command == "match":
        from matcher.batch_score import batch_score

        batch_score(min_grade=args.min_grade, limit=args.limit)
    elif args.command == "apply":
        from applier.run import run_applier

        run_applier(
            min_grade=args.min_grade,
            max_daily=args.max_daily,
            dry_run=False if args.real else None,
            sleep_between=args.sleep_between,
        )
    elif args.command == "dashboard":
        subprocess.run(["go", "run", "./dashboard"], check=True)
    elif args.command == "report":
        from reports.generate import generate_daily_report

        generate_daily_report()
    elif args.command == "schedule":
        from batch.scheduler import start_scheduler

        start_scheduler()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

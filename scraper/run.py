from __future__ import annotations

import argparse
from importlib import import_module
from dataclasses import replace

from common.config import load_dotenv, load_yaml
from common.db import Database
from scraper.base import JobSearchFilters, Scraper


SCRAPER_MODULES: dict[str, tuple[str, str]] = {
    "linkedin": ("scraper.linkedin", "LinkedInScraper"),
    "indeed": ("scraper.indeed", "IndeedScraper"),
    "naukri": ("scraper.naukri", "NaukriScraper"),
    "wellfound": ("scraper.wellfound", "WellfoundScraper"),
}


def scraper_class(platform: str) -> type[Scraper]:
    module_name, class_name = SCRAPER_MODULES[platform]
    module = import_module(module_name)
    return getattr(module, class_name)


def configured_filters() -> tuple[list[str], list[str], dict]:
    config = load_yaml("config/filters.yaml")
    roles = config.get("roles") or ["Data Engineer", "AI Engineer", "MLOps Engineer"]
    locations = config.get("locations") or ["Remote"]
    return roles, locations, config


def enabled_platforms(config: dict, requested: str | None = None, all_enabled: bool = False) -> list[str]:
    if requested:
        return [requested]
    platforms = config.get("platforms", {})
    if all_enabled:
        return [name for name, is_enabled in platforms.items() if is_enabled]
    return ["linkedin"]


def scrape_once(
    platform: str,
    filters: JobSearchFilters,
    db: Database,
    excluded_companies: list[str] | None = None,
    excluded_keywords: list[str] | None = None,
) -> tuple[int, int]:
    scraper = scraper_class(platform)()
    run_id = db.start_scraper_run(platform, filters.role, filters.location)
    jobs_found = 0
    jobs_inserted = 0
    try:
        jobs = scraper.scrape(filters)
        jobs_found = len(jobs)
        for job in jobs:
            company = job.company.lower()
            text = f"{job.title}\n{job.company}\n{job.jd_text}".lower()
            if not filters.location_matches(job.location):
                continue
            if any(company == item.lower() for item in excluded_companies or []):
                continue
            if any(keyword.lower() in text for keyword in excluded_keywords or []):
                continue
            if db.insert_job(job.to_db_record()):
                jobs_inserted += 1
        db.finish_scraper_run(run_id, jobs_found, jobs_inserted)
    except Exception as exc:
        db.finish_scraper_run(run_id, jobs_found, jobs_inserted, "failed", str(exc))
        raise
    return jobs_found, jobs_inserted


def run_scrapers(platform: str | None = None, all_enabled: bool = False, limit: int | None = None) -> None:
    load_dotenv()
    db = Database()
    roles, locations, config = configured_filters()
    platforms = enabled_platforms(config, requested=platform, all_enabled=all_enabled)
    filters_template = JobSearchFilters(
        role=roles[0],
        location=locations[0],
        remote=bool(config.get("remote", False)),
        salary_min=config.get("salary_min"),
        date_posted_within_days=int(config.get("date_posted_within_days", 3)),
        experience_years=config.get("experience_years"),
    )

    runs = 0
    for platform_name in platforms:
        if platform_name not in SCRAPER_MODULES:
            raise ValueError(f"Unknown platform: {platform_name}")
        for role in roles:
            for location in locations:
                filters = replace(filters_template, role=role, location=location)
                found, inserted = scrape_once(
                    platform_name,
                    filters,
                    db,
                    excluded_companies=config.get("excluded_companies", []),
                    excluded_keywords=config.get("excluded_keywords", []),
                )
                print(f"{platform_name}: {role} in {location}: found={found} inserted={inserted}")
                runs += 1
                if limit and runs >= limit:
                    return


def preview_scrape_plan(
    platform: str | None = None, all_enabled: bool = False, limit: int | None = None
) -> None:
    load_dotenv()
    roles, locations, config = configured_filters()
    platforms = enabled_platforms(config, requested=platform, all_enabled=all_enabled)
    filters_template = JobSearchFilters(
        role=roles[0],
        location=locations[0],
        remote=bool(config.get("remote", False)),
        salary_min=config.get("salary_min"),
        date_posted_within_days=int(config.get("date_posted_within_days", 3)),
        experience_years=config.get("experience_years"),
    )

    runs = 0
    for platform_name in platforms:
        for role in roles:
            for location in locations:
                filters = replace(filters_template, role=role, location=location)
                print(
                    f"{platform_name}: role='{role}' location='{location}' "
                    f"query='{filters.keyword_query()}' remote={filters.remote}"
                )
                runs += 1
                if limit and runs >= limit:
                    return


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AutoApply scrapers.")
    parser.add_argument("--platform", choices=sorted(SCRAPER_MODULES.keys()))
    parser.add_argument("--all-enabled", action="store_true")
    parser.add_argument("--limit", type=int, help="Limit scraper role/location combinations.")
    parser.add_argument("--preview", action="store_true", help="Print scrape matrix without DB/network.")
    args = parser.parse_args()
    if args.preview:
        preview_scrape_plan(platform=args.platform, all_enabled=args.all_enabled, limit=args.limit)
        return
    run_scrapers(platform=args.platform, all_enabled=args.all_enabled, limit=args.limit)


if __name__ == "__main__":
    main()

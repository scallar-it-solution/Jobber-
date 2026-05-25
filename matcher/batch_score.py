from __future__ import annotations

import argparse
import json

from common.config import load_dotenv, load_yaml
from common.db import Database
from matcher.resume_parser import extract_resume_text
from matcher.score import score_job


def batch_score(min_grade: str = "B", limit: int = 100) -> list[dict]:
    load_dotenv()
    db = Database()
    resume_text = extract_resume_text()
    jobs = db.fetch_jobs_for_scoring(limit=limit)
    results: list[dict] = []
    for job in jobs:
        result = score_job(
            str(job["id"]),
            min_grade=min_grade,
            db=db,
            resume_text=resume_text,
        )
        results.append(result)
        print(
            f"{result['job_id']} grade={result['match_grade']} "
            f"score={result['composite_score']:.2f} status={result['status']}"
        )
    return results


def main() -> None:
    load_dotenv()
    filters = load_yaml("config/filters.yaml")
    parser = argparse.ArgumentParser(description="Batch score new jobs.")
    parser.add_argument("--min-grade", default=filters.get("min_match_grade", "B"))
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    results = batch_score(args.min_grade, args.limit)
    if args.json:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()


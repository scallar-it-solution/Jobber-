from __future__ import annotations

import argparse
import json

from common.config import load_dotenv, load_yaml
from common.db import Database
from matcher.resume_parser import extract_resume_text
from matcher.scoring import grade_meets_threshold, score_match


def score_job(
    job_id: str,
    min_grade: str = "B",
    resume_path: str = "data/resume/data_engineer_resume.pdf",
    db: Database | None = None,
    resume_text: str | None = None,
) -> dict:
    database = db or Database()
    job = database.fetch_job(job_id)
    if not job:
        raise ValueError(f"Job not found: {job_id}")

    text = resume_text if resume_text is not None else extract_resume_text(resume_path)
    result = score_match(text, job.get("jd_text") or "")
    status = "queued" if grade_meets_threshold(result["match_grade"], min_grade) else "matched"
    database.update_job_scores(
        str(job["id"]),
        result["ats_score"],
        result["semantic_score"],
        result["composite_score"],
        result["match_grade"],
        result["missing_keywords"],
        status,
    )
    return {"job_id": str(job["id"]), "status": status, **result}


def main() -> None:
    load_dotenv()
    filters = load_yaml("config/filters.yaml")
    parser = argparse.ArgumentParser(description="Score one job against the resume.")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--resume", default="data/resume/data_engineer_resume.pdf")
    parser.add_argument("--min-grade", default=filters.get("min_match_grade", "B"))
    args = parser.parse_args()
    print(json.dumps(score_job(args.job_id, args.min_grade, args.resume), indent=2))


if __name__ == "__main__":
    main()


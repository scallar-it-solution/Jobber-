from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class JobSearchFilters:
    role: str
    location: str | None = None
    remote: bool = True
    salary_min: int | None = None
    date_posted_within_days: int = 3
    experience_years: int | None = None

    def keyword_query(self) -> str:
        if self.experience_years is None:
            return self.role
        return f"{self.role} {self.experience_years} year experience junior"

    def location_aliases(self) -> set[str]:
        location = (self.location or "").strip().lower()
        if not location:
            return set()
        aliases = {location}
        if location in {"gurgaon", "gurugram"}:
            aliases.update({"gurgaon", "gurugram"})
        if location == "noida":
            aliases.update({"noida", "greater noida"})
        return aliases

    def location_matches(self, value: str | None) -> bool:
        aliases = self.location_aliases()
        if not aliases:
            return True
        normalized = (value or "").lower()
        if self.remote and "remote" in normalized:
            return True
        return any(alias in normalized for alias in aliases)


@dataclass
class JobRecord:
    platform: str
    title: str
    company: str
    location: str | None
    jd_text: str
    apply_url: str
    salary: str | None = None
    posted_at: datetime | None = None
    status: str = "new"
    id: str | None = None
    scraped_at: datetime | None = None

    def dedupe_hash(self) -> str:
        key = f"{self.title.strip().lower()}::{self.company.strip().lower()}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def to_db_record(self) -> dict[str, Any]:
        scraped_at = self.scraped_at or datetime.now(timezone.utc)
        return {
            "id": self.id or str(uuid.uuid4()),
            "platform": self.platform,
            "title": self.title.strip(),
            "company": self.company.strip(),
            "location": (self.location or "").strip(),
            "jd_text": self.jd_text.strip(),
            "apply_url": self.apply_url.strip(),
            "salary": self.salary,
            "posted_at": self.posted_at,
            "scraped_at": scraped_at,
            "status": self.status,
            "dedupe_hash": self.dedupe_hash(),
        }


class Scraper:
    platform = "base"

    def scrape(self, filters: JobSearchFilters) -> list[JobRecord]:
        raise NotImplementedError

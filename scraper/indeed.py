from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup

from common.rate_limit import proxy_for_requests, random_delay, random_user_agent
from scraper.base import JobRecord, JobSearchFilters, Scraper


class IndeedScraper(Scraper):
    platform = "indeed"
    base_url = "https://www.indeed.com"

    def scrape(self, filters: JobSearchFilters) -> list[JobRecord]:
        params = {
            "q": filters.keyword_query(),
            "l": filters.location or "Remote",
            "fromage": filters.date_posted_within_days,
        }
        url = f"{self.base_url}/jobs?{urlencode(params)}"
        session = requests.Session()
        headers = {"User-Agent": random_user_agent(), "Accept-Language": "en-US,en;q=0.9"}
        response = session.get(url, headers=headers, proxies=proxy_for_requests(), timeout=25)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        cards = soup.select("div.job_seen_beacon, div[data-jk], a.tapItem")
        jobs: list[JobRecord] = []

        for card in cards[:30]:
            title_el = card.select_one("h2.jobTitle span[title], h2.jobTitle span, a[data-jk]")
            company_el = card.select_one("[data-testid='company-name'], span.companyName")
            location_el = card.select_one("[data-testid='text-location'], div.companyLocation")
            salary_el = card.select_one(".salary-snippet-container, [data-testid='attribute_snippet_testid']")
            link_el = card.select_one("a[href]")
            if not title_el or not company_el:
                continue

            apply_url = urljoin(self.base_url, link_el.get("href", "")) if link_el else url
            jd_text = self._fetch_description(session, apply_url, headers)
            jobs.append(
                JobRecord(
                    platform=self.platform,
                    title=title_el.get_text(" ", strip=True),
                    company=company_el.get_text(" ", strip=True),
                    location=location_el.get_text(" ", strip=True) if location_el else filters.location,
                    jd_text=jd_text,
                    apply_url=apply_url,
                    salary=salary_el.get_text(" ", strip=True) if salary_el else None,
                    posted_at=None,
                    scraped_at=datetime.now(timezone.utc),
                )
            )
            random_delay()

        return jobs

    def _fetch_description(
        self, session: requests.Session, apply_url: str, headers: dict[str, str]
    ) -> str:
        try:
            response = session.get(
                apply_url, headers=headers, proxies=proxy_for_requests(), timeout=25
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            description = soup.select_one("#jobDescriptionText")
            return description.get_text("\n", strip=True) if description else soup.get_text("\n", strip=True)
        except requests.RequestException:
            return ""

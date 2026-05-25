from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode

from common.rate_limit import proxy_for_playwright, random_delay, random_user_agent
from scraper.base import JobRecord, JobSearchFilters, Scraper


class NaukriScraper(Scraper):
    platform = "naukri"

    def scrape(self, filters: JobSearchFilters) -> list[JobRecord]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Install Playwright and run: playwright install chromium") from exc

        params = {
            "k": filters.keyword_query(),
            "l": filters.location or "Remote",
            "jobAge": filters.date_posted_within_days,
        }
        if filters.experience_years is not None:
            params["experience"] = filters.experience_years
        url = f"https://www.naukri.com/jobs?{urlencode(params)}"
        jobs: list[JobRecord] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, proxy=proxy_for_playwright())
            page = browser.new_page(user_agent=random_user_agent(), locale="en-IN")
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            cards = page.locator("article.jobTuple, div.srp-jobtuple-wrapper").all()
            for card in cards[:25]:
                title = self._safe_text(card, "a.title, a.titleAnchor")
                company = self._safe_text(card, "a.subTitle, a.comp-name")
                location_text = self._safe_text(card, ".locWdth, .loc")
                salary = self._safe_text(card, ".salary, .sal-wrap")
                apply_url = self._safe_attr(card, "a.title, a.titleAnchor", "href") or url
                jd_text = self._safe_text(card, ".job-description, .job-desc")
                if title and company:
                    jobs.append(
                        JobRecord(
                            platform=self.platform,
                            title=title,
                            company=company,
                            location=location_text or filters.location,
                            jd_text=jd_text,
                            apply_url=apply_url,
                            salary=salary or None,
                            scraped_at=datetime.now(timezone.utc),
                        )
                    )
                random_delay()
            browser.close()
        return jobs

    def _safe_text(self, locator, selector: str) -> str:
        try:
            child = locator.locator(selector).first
            return child.inner_text(timeout=1500).strip() if child.count() else ""
        except Exception:
            return ""

    def _safe_attr(self, locator, selector: str, attr: str) -> str:
        try:
            child = locator.locator(selector).first
            return child.get_attribute(attr, timeout=1500) or ""
        except Exception:
            return ""

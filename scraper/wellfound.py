from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode

from common.rate_limit import proxy_for_playwright, random_delay, random_user_agent
from scraper.base import JobRecord, JobSearchFilters, Scraper


class WellfoundScraper(Scraper):
    platform = "wellfound"

    def scrape(self, filters: JobSearchFilters) -> list[JobRecord]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Install Playwright and run: playwright install chromium") from exc

        params = {"role": filters.keyword_query(), "location": filters.location or "Remote"}
        url = f"https://wellfound.com/jobs?{urlencode(params)}"
        jobs: list[JobRecord] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, proxy=proxy_for_playwright())
            page = browser.new_page(user_agent=random_user_agent(), locale="en-US")
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            cards = page.locator("[data-test='JobSearchResult'], div.styles_component__UCLp3").all()
            for card in cards[:25]:
                title = self._safe_text(card, "a, h3, h4")
                company = self._safe_text(card, "[data-test='StartupName'], h2, h3")
                location = self._safe_text(card, "[data-test='Location'], span")
                apply_url = self._safe_attr(card, "a[href]", "href") or url
                jd_text = card.inner_text(timeout=3000).strip()
                if title and company:
                    jobs.append(
                        JobRecord(
                            platform=self.platform,
                            title=title,
                            company=company,
                            location=location or filters.location,
                            jd_text=jd_text,
                            apply_url=apply_url,
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
            value = child.get_attribute(attr, timeout=1500) if child.count() else ""
            if value and value.startswith("/"):
                return f"https://wellfound.com{value}"
            return value or ""
        except Exception:
            return ""

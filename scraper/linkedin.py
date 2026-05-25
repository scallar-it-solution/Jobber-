from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from common.config import project_root
from common.rate_limit import proxy_for_playwright, random_delay, random_user_agent
from scraper.base import JobRecord, JobSearchFilters, Scraper


class LinkedInScraper(Scraper):
    platform = "linkedin"

    def scrape(self, filters: JobSearchFilters) -> list[JobRecord]:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Install Playwright and run: playwright install chromium") from exc

        query = {
            "keywords": filters.keyword_query(),
            "location": filters.location or "Remote",
            "f_TPR": f"r{filters.date_posted_within_days * 86400}",
        }
        if filters.remote:
            query["f_WT"] = "2"
        search_url = f"https://www.linkedin.com/jobs/search/?{urlencode(query)}"

        jobs: list[JobRecord] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, proxy=proxy_for_playwright())
            context = browser.new_context(user_agent=random_user_agent(), locale="en-US")
            self._load_cookies(context)
            page = context.new_page()
            page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)

            cards = page.locator(".jobs-search-results__list-item, .job-card-container").all()
            for index, card in enumerate(cards[:25]):
                try:
                    card.scroll_into_view_if_needed()
                    card.click(timeout=5000)
                    page.wait_for_timeout(1500)
                    title = self._first_text(
                        page,
                        [
                            ".job-details-jobs-unified-top-card__job-title",
                            "h1",
                            ".jobs-unified-top-card__job-title",
                        ],
                    )
                    company = self._first_text(
                        page,
                        [
                            ".job-details-jobs-unified-top-card__company-name",
                            ".jobs-unified-top-card__company-name",
                        ],
                    )
                    location = self._first_text(
                        page,
                        [
                            ".job-details-jobs-unified-top-card__primary-description-container",
                            ".jobs-unified-top-card__bullet",
                        ],
                    )
                    jd_text = self._first_text(
                        page,
                        [
                            ".jobs-description__content",
                            ".jobs-box__html-content",
                            "#job-details",
                        ],
                    )
                    apply_url = page.url
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
                except PlaywrightTimeoutError:
                    continue
                except Exception:
                    continue

            context.close()
            browser.close()

        return jobs

    def _load_cookies(self, context) -> None:
        cookies_path = Path(
            os.getenv("LINKEDIN_COOKIES_PATH", str(project_root() / "config/linkedin_cookies.json"))
        )
        if not cookies_path.exists():
            return
        cookies = json.loads(cookies_path.read_text(encoding="utf-8"))
        context.add_cookies(cookies)

    def _first_text(self, page, selectors: list[str]) -> str:
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                if locator.count() and locator.is_visible(timeout=1000):
                    text = locator.inner_text(timeout=2000).strip()
                    if text:
                        return text
            except Exception:
                continue
        return ""

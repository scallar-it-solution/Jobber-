from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from common.artifacts import save_page_artifacts
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
            browser = p.chromium.launch(
                headless=True,
                proxy=proxy_for_playwright(),
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )
            context = browser.new_context(
                user_agent=random_user_agent(),
                locale="en-US",
                timezone_id="Asia/Kolkata",
                viewport={"width": 1366, "height": 900},
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            )
            has_cookies = self._load_cookies(context)
            page = context.new_page()
            page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(4500)
            self._scroll_results(page)

            if self._looks_blocked(page):
                save_page_artifacts(page, f"linkedin-blocked-{filters.role}-{filters.location}")

            cards = self._job_cards(page)
            if not cards:
                label = "linkedin-empty-auth" if has_cookies else "linkedin-empty-no-cookies"
                save_page_artifacts(page, f"{label}-{filters.role}-{filters.location}")
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
                            ".top-card-layout__title",
                            ".base-search-card__title",
                        ],
                    )
                    company = self._first_text(
                        page,
                        [
                            ".job-details-jobs-unified-top-card__company-name",
                            ".jobs-unified-top-card__company-name",
                            ".topcard__org-name-link",
                            ".base-search-card__subtitle",
                        ],
                    )
                    location = self._first_text(
                        page,
                        [
                            ".job-details-jobs-unified-top-card__primary-description-container",
                            ".jobs-unified-top-card__bullet",
                            ".topcard__flavor--bullet",
                            ".job-search-card__location",
                        ],
                    )
                    jd_text = self._first_text(
                        page,
                        [
                            ".jobs-description__content",
                            ".jobs-box__html-content",
                            "#job-details",
                            ".show-more-less-html",
                            ".description__text",
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

    def _load_cookies(self, context) -> bool:
        cookies_path = Path(
            os.getenv("LINKEDIN_COOKIES_PATH", str(project_root() / "config/linkedin_cookies.json"))
        )
        if not cookies_path.exists():
            return False
        cookies = json.loads(cookies_path.read_text(encoding="utf-8"))
        context.add_cookies(cookies)
        return True

    def _looks_blocked(self, page) -> bool:
        url = page.url.lower()
        if any(part in url for part in ["login", "checkpoint", "authwall", "uas/login"]):
            return True
        text = ""
        try:
            text = page.locator("body").inner_text(timeout=2000).lower()
        except Exception:
            return False
        return any(term in text for term in ["sign in", "security verification", "captcha", "authwall"])

    def _scroll_results(self, page) -> None:
        for _ in range(3):
            page.mouse.wheel(0, 1400)
            page.wait_for_timeout(1200)

    def _job_cards(self, page) -> list:
        selectors = [
            ".jobs-search-results__list-item",
            ".job-card-container",
            ".base-card",
            ".job-search-card",
            "li[data-occludable-job-id]",
        ]
        for selector in selectors:
            try:
                page.wait_for_selector(selector, timeout=7000)
                cards = page.locator(selector).all()
                if cards:
                    return cards
            except Exception:
                continue
        return []

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

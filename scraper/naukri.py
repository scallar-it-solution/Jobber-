from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlencode

from common.artifacts import save_page_artifacts
from common.rate_limit import proxy_for_playwright, random_delay, random_user_agent
from scraper.base import JobRecord, JobSearchFilters, Scraper


class NaukriScraper(Scraper):
    platform = "naukri"

    def scrape(self, filters: JobSearchFilters) -> list[JobRecord]:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Install Playwright and run: playwright install chromium") from exc

        url = self._search_url(filters)
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
                locale="en-IN",
                timezone_id="Asia/Kolkata",
                viewport={"width": 1366, "height": 900},
                extra_http_headers={"Accept-Language": "en-IN,en;q=0.9"},
            )
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(4500)
                self._dismiss_popups(page)
                self._scroll_results(page)
                cards = self._job_cards(page)
                if not cards:
                    save_page_artifacts(page, f"naukri-empty-{filters.role}-{filters.location}")
                for card in cards[:25]:
                    title = self._safe_text(
                        card, "a.title, a.titleAnchor, a[href*='job-listings'], a[class*='title']"
                    )
                    company = self._safe_text(card, "a.subTitle, a.comp-name, a[class*='comp']")
                    location_text = self._safe_text(card, ".locWdth, .loc, span[class*='loc']")
                    salary = self._safe_text(card, ".salary, .sal-wrap, span[class*='sal']")
                    apply_url = self._safe_attr(
                        card, "a.title, a.titleAnchor, a[href*='job-listings'], a[class*='title']", "href"
                    ) or url
                    jd_text = self._safe_text(card, ".job-description, .job-desc, span[class*='desc']")
                    if not jd_text:
                        jd_text = self._safe_text(card, "*")
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
                    random_delay(0.8, 1.8)
            except PlaywrightTimeoutError:
                save_page_artifacts(page, f"naukri-timeout-{filters.role}-{filters.location}")
            finally:
                context.close()
                browser.close()
        return jobs

    def _search_url(self, filters: JobSearchFilters) -> str:
        role_slug = self._slug(filters.role)
        location_slug = self._slug(filters.location or "india")
        params = {
            "jobAge": filters.date_posted_within_days,
        }
        if filters.experience_years is not None:
            params["experience"] = filters.experience_years
        return f"https://www.naukri.com/{role_slug}-jobs-in-{location_slug}?{urlencode(params)}"

    def _slug(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

    def _dismiss_popups(self, page) -> None:
        for selector in ["button:has-text('Got it')", "button:has-text('Later')", ".crossIcon", ".close"]:
            try:
                locator = page.locator(selector).first
                if locator.count() and locator.is_visible(timeout=800):
                    locator.click(timeout=1500)
            except Exception:
                continue

    def _scroll_results(self, page) -> None:
        for _ in range(3):
            page.mouse.wheel(0, 1400)
            page.wait_for_timeout(1200)

    def _job_cards(self, page) -> list:
        selectors = [
            "article.jobTuple",
            "div.srp-jobtuple-wrapper",
            "div.cust-job-tuple",
            "div[class*='jobTuple']",
            "div[class*='srp-jobtuple']",
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

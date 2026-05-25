from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from applier.base import ApplyResult
from applier.llm import answer_screening_question
from common.config import project_root
from common.rate_limit import proxy_for_playwright, random_delay, random_user_agent


class IndeedQuickApplyBot:
    platform = "indeed"

    def apply(self, job: dict[str, Any], profile: dict[str, Any], dry_run: bool = True) -> ApplyResult:
        if dry_run:
            return ApplyResult(
                status="dry_run",
                message="Dry run only; Indeed application was not submitted.",
                payload={"apply_url": job.get("apply_url")},
            )

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Install Playwright and run: playwright install chromium") from exc

        resume_path = Path(profile.get("resume_path", "data/resume/data_engineer_resume.pdf"))
        if not resume_path.is_absolute():
            resume_path = project_root() / resume_path

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, proxy=proxy_for_playwright())
            page = browser.new_page(user_agent=random_user_agent(), locale="en-US")
            page.goto(job["apply_url"], wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2500)
            apply_button = page.get_by_role("button", name=re.compile("apply", re.I))
            if not apply_button.count():
                browser.close()
                return ApplyResult("failed", "Indeed quick apply button not found.")

            apply_button.first.click(timeout=10000)
            page.wait_for_timeout(2000)
            self._fill_fields(page, profile)
            for file_input in page.locator("input[type='file']").all():
                try:
                    file_input.set_input_files(str(resume_path), timeout=3000)
                except Exception:
                    continue

            steps = 0
            for _ in range(8):
                self._fill_fields(page, profile)
                next_button = page.locator(
                    "button",
                    has_text=re.compile(r"(continue|review|submit)", re.I),
                )
                if not next_button.count():
                    break
                label = next_button.first.inner_text(timeout=1000).strip().lower()
                next_button.first.click(timeout=10000)
                steps += 1
                random_delay(1.5, 3.0)
                if "submit" in label:
                    break
            browser.close()
            return ApplyResult("applied", "Indeed quick apply submitted.", {"steps": steps})

    def _fill_fields(self, page, profile: dict[str, Any]) -> None:
        values = {
            "email": profile.get("email", ""),
            "phone": profile.get("phone", ""),
            "name": profile.get("name", ""),
            "experience": str(profile.get("years_experience", "")),
        }
        for field in page.locator("input, textarea").all():
            try:
                label = (
                    field.get_attribute("aria-label")
                    or field.get_attribute("placeholder")
                    or field.get_attribute("name")
                    or ""
                ).lower()
                if field.evaluate("el => el.tagName.toLowerCase()") == "textarea" and not field.input_value():
                    field.fill(answer_screening_question(label or "screening question", profile))
                    continue
                for key, value in values.items():
                    if key in label and value:
                        field.fill(str(value), timeout=1500)
                        break
            except Exception:
                continue

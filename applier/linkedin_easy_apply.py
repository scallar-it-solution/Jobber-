from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from applier.base import ApplyResult
from applier.llm import answer_screening_question
from common.config import project_root
from common.rate_limit import proxy_for_playwright, random_delay, random_user_agent


class LinkedInEasyApplyBot:
    platform = "linkedin"

    def apply(self, job: dict[str, Any], profile: dict[str, Any], dry_run: bool = True) -> ApplyResult:
        if dry_run:
            return ApplyResult(
                status="dry_run",
                message="Dry run only; LinkedIn application was not submitted.",
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
            context = browser.new_context(user_agent=random_user_agent(), locale="en-US")
            self._load_cookies(context)
            page = context.new_page()
            page.goto(job["apply_url"], wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2500)

            easy_apply = page.get_by_role("button", name=re.compile("easy apply", re.I))
            if not easy_apply.count():
                browser.close()
                return ApplyResult("failed", "Easy Apply button not found.")

            easy_apply.first.click(timeout=10000)
            page.wait_for_timeout(2000)
            self._fill_known_fields(page, profile)
            self._upload_resume(page, resume_path)
            self._answer_visible_questions(page, profile)

            submit_count = self._walk_steps(page, profile)
            browser.close()
            return ApplyResult("applied", "LinkedIn Easy Apply submitted.", {"steps": submit_count})

    def _load_cookies(self, context) -> None:
        cookies_path = Path(
            os.getenv("LINKEDIN_COOKIES_PATH", str(project_root() / "config/linkedin_cookies.json"))
        )
        if cookies_path.exists():
            context.add_cookies(json.loads(cookies_path.read_text(encoding="utf-8")))

    def _fill_known_fields(self, page, profile: dict[str, Any]) -> None:
        known = {
            "email": profile.get("email", ""),
            "phone": profile.get("phone", ""),
            "mobile": profile.get("phone", ""),
            "years": str(profile.get("years_experience", "")),
        }
        for input_box in page.locator("input, textarea").all():
            try:
                label = (
                    input_box.get_attribute("aria-label")
                    or input_box.get_attribute("placeholder")
                    or input_box.get_attribute("name")
                    or ""
                ).lower()
                for key, value in known.items():
                    if key in label and value:
                        input_box.fill(str(value), timeout=1500)
                        break
            except Exception:
                continue

    def _upload_resume(self, page, resume_path: Path) -> None:
        for file_input in page.locator("input[type='file']").all():
            try:
                file_input.set_input_files(str(resume_path), timeout=3000)
            except Exception:
                continue

    def _answer_visible_questions(self, page, profile: dict[str, Any]) -> None:
        for textarea in page.locator("textarea").all():
            try:
                current = textarea.input_value(timeout=1000)
                if current:
                    continue
                label = textarea.get_attribute("aria-label") or "screening question"
                textarea.fill(answer_screening_question(label, profile), timeout=2000)
            except Exception:
                continue

    def _walk_steps(self, page, profile: dict[str, Any]) -> int:
        steps = 0
        for _ in range(8):
            self._fill_known_fields(page, profile)
            self._answer_visible_questions(page, profile)
            next_button = page.locator(
                "button",
                has_text=re.compile(r"^(next|review|submit application)$", re.I),
            )
            if not next_button.count():
                break
            label = next_button.first.inner_text(timeout=1000).strip().lower()
            next_button.first.click(timeout=10000)
            steps += 1
            random_delay(1.5, 3.0)
            if "submit" in label:
                break
        return steps

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from common.config import project_root


def artifact_dir() -> Path:
    path = Path(os.getenv("SCRAPER_DEBUG_DIR", "reports/debug"))
    if not path.is_absolute():
        path = project_root() / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def artifact_name(label: str, suffix: str) -> Path:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "-", label).strip("-").lower()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return artifact_dir() / f"{stamp}-{cleaned}.{suffix}"


def save_page_artifacts(page, label: str) -> None:
    html_path = artifact_name(label, "html")
    png_path = artifact_name(label, "png")
    try:
        html_path.write_text(page.content(), encoding="utf-8")
    except Exception:
        pass
    try:
        page.screenshot(path=str(png_path), full_page=True, timeout=10000)
    except Exception:
        pass


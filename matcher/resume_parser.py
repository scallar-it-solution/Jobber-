from __future__ import annotations

from pathlib import Path

from common.config import project_root


def extract_resume_text(path: str | Path = "data/resume/data_engineer_resume.pdf") -> str:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Install PyMuPDF first: pip install -r requirements.txt") from exc

    resume_path = Path(path)
    if not resume_path.is_absolute():
        resume_path = project_root() / resume_path
    if not resume_path.exists():
        fallback = project_root() / "data_engineer_resume.pdf"
        if fallback.exists():
            resume_path = fallback
        else:
            raise FileNotFoundError(f"Resume PDF not found: {resume_path}")

    text_parts: list[str] = []
    with fitz.open(resume_path) as doc:
        for page in doc:
            text_parts.append(page.get_text("text"))
    return "\n".join(text_parts).strip()


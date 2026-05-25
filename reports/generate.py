from __future__ import annotations

from datetime import date
from pathlib import Path

from common.config import load_dotenv, project_root
from common.db import Database


def _html_escape(value) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def collect_daily_metrics(db: Database) -> dict:
    with db.connect() as conn:
        scraped = conn.execute(
            """
            SELECT platform, COUNT(*) AS count
            FROM jobs
            WHERE scraped_at::date = CURRENT_DATE
            GROUP BY platform
            ORDER BY platform
            """
        ).fetchall()
        top_matches = conn.execute(
            """
            SELECT company, title, composite_score, match_grade, status
            FROM jobs
            WHERE scraped_at::date = CURRENT_DATE
            ORDER BY composite_score DESC NULLS LAST
            LIMIT 10
            """
        ).fetchall()
        applications = conn.execute(
            """
            SELECT
              COUNT(*) AS total,
              COUNT(*) FILTER (WHERE status = 'applied') AS applied,
              COUNT(*) FILTER (WHERE status = 'failed') AS failed,
              COUNT(*) FILTER (WHERE dry_run = true) AS dry_runs
            FROM applications
            WHERE applied_at::date = CURRENT_DATE
            """
        ).fetchone()
        missing = conn.execute(
            """
            SELECT keyword, COUNT(*) AS count
            FROM jobs
            CROSS JOIN LATERAL jsonb_array_elements_text(missing_keywords) AS keyword
            WHERE scraped_at >= NOW() - INTERVAL '7 days'
            GROUP BY keyword
            ORDER BY count DESC
            LIMIT 15
            """
        ).fetchall()

    return {
        "scraped": scraped,
        "top_matches": top_matches,
        "applications": applications,
        "missing": missing,
    }


def render_html(metrics: dict, report_date: date) -> str:
    scraped_rows = "".join(
        f"<tr><td>{_html_escape(row['platform'])}</td><td>{row['count']}</td></tr>"
        for row in metrics["scraped"]
    )
    top_rows = "".join(
        "<tr>"
        f"<td>{_html_escape(row['company'])}</td>"
        f"<td>{_html_escape(row['title'])}</td>"
        f"<td>{float(row['composite_score'] or 0):.2f}</td>"
        f"<td>{_html_escape(row['match_grade'])}</td>"
        f"<td>{_html_escape(row['status'])}</td>"
        "</tr>"
        for row in metrics["top_matches"]
    )
    missing_rows = "".join(
        f"<tr><td>{_html_escape(row['keyword'])}</td><td>{row['count']}</td></tr>"
        for row in metrics["missing"]
    )
    app = metrics["applications"] or {}
    total = int(app.get("total", 0) or 0)
    applied = int(app.get("applied", 0) or 0)
    success_rate = (applied / total * 100) if total else 0.0

    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>AutoApply Daily Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; color: #17202a; margin: 32px; }}
    h1 {{ margin-bottom: 4px; }}
    h2 {{ margin-top: 28px; border-bottom: 1px solid #d5d8dc; padding-bottom: 6px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
    th, td {{ border: 1px solid #d5d8dc; padding: 8px; text-align: left; }}
    th {{ background: #eef2f7; }}
    .metric {{ display: inline-block; margin-right: 24px; }}
  </style>
</head>
<body>
  <h1>AutoApply Daily Report</h1>
  <p>{report_date.isoformat()}</p>

  <h2>Applications</h2>
  <p>
    <span class="metric">Total: {total}</span>
    <span class="metric">Applied: {applied}</span>
    <span class="metric">Failed: {int(app.get("failed", 0) or 0)}</span>
    <span class="metric">Dry runs: {int(app.get("dry_runs", 0) or 0)}</span>
    <span class="metric">Success rate: {success_rate:.1f}%</span>
  </p>

  <h2>Jobs Scraped Today</h2>
  <table><thead><tr><th>Platform</th><th>Count</th></tr></thead><tbody>{scraped_rows}</tbody></table>

  <h2>Top 10 Matched Jobs</h2>
  <table>
    <thead><tr><th>Company</th><th>Role</th><th>Score</th><th>Grade</th><th>Status</th></tr></thead>
    <tbody>{top_rows}</tbody>
  </table>

  <h2>Missing Skills Trend</h2>
  <table><thead><tr><th>Keyword</th><th>Count</th></tr></thead><tbody>{missing_rows}</tbody></table>
</body>
</html>
"""


def generate_daily_report(output_path: str | Path | None = None) -> Path:
    load_dotenv()
    db = Database()
    report_date = date.today()
    reports_dir = project_root() / "reports"
    reports_dir.mkdir(exist_ok=True)
    pdf_path = Path(output_path) if output_path else reports_dir / f"{report_date.isoformat()}.pdf"
    html_path = pdf_path.with_suffix(".html")

    html = render_html(collect_daily_metrics(db), report_date)
    html_path.write_text(html, encoding="utf-8")
    try:
        from weasyprint import HTML

        HTML(string=html).write_pdf(pdf_path)
        print(f"Report written: {pdf_path}")
        return pdf_path
    except Exception as exc:
        print(f"PDF generation skipped ({exc}). HTML written: {html_path}")
        return html_path


def main() -> None:
    generate_daily_report()


if __name__ == "__main__":
    main()


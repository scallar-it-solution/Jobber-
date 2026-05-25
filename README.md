# AutoApply

Autonomous job search, matching, and application pipeline for Deepesh Patel's Data and AI Engineer search.

This repo is scaffolded to run locally first, then deploy to AWS. The local path is:

1. Scrape jobs into PostgreSQL.
2. Score each job description against `data/resume/data_engineer_resume.pdf`.
3. Queue A/B matches.
4. Dry-run application bots by default.
5. Generate a daily report.

Use real application mode only after you have reviewed platform rules, your profile values, and the queued jobs.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
copy .env.example .env
docker compose up -d
.\autoapply.cmd init-db
.\autoapply.cmd scrape --platform linkedin --limit 1
.\autoapply.cmd match
.\autoapply.cmd apply
.\autoapply.cmd report
```

To test matching and reporting without a live scraper run:

```powershell
python scripts\seed_sample_job.py
.\autoapply.cmd match
.\autoapply.cmd apply
.\autoapply.cmd report
```

`APPLIER_DRY_RUN=true` is set in `.env.example`, so `apply` records a dry run instead of submitting applications. To submit real applications, set `APPLIER_DRY_RUN=false` or run:

```powershell
.\autoapply.cmd apply --real --sleep-between
```

## Commands

```powershell
.\autoapply.cmd start              # init DB, scrape, match, dry-run apply, report
.\autoapply.cmd scrape             # LinkedIn scrape only by default
.\autoapply.cmd scrape --all-enabled
.\autoapply.cmd phase1             # Gurgaon/Noida Data Engineer + Cloud Engineer listings
.\autoapply.cmd match --min-grade B
.\autoapply.cmd apply              # dry-run unless APPLIER_DRY_RUN=false
.\autoapply.cmd dashboard
.\autoapply.cmd report
.\autoapply.cmd schedule
```

## Project Layout

```text
scraper/          Job board scrapers
matcher/          Resume to job-description scoring
applier/          Platform apply bots
dashboard/        Go Bubble Tea dashboard
batch/            Pipeline scheduler and orchestration
config/           Profile, filters, cookie examples
data/             Schema and resume storage
reports/          Daily report output
infra/            AWS Terraform scaffolding
```

## Reference Repositories

Fetch the requested upstream references with shallow clones:

```powershell
.\scripts\fetch_reference_repos.ps1
```

Notes on how their ideas map into this repo are in `docs/reference-projects.md`.

## Phase 1 Target

The first job-listing phase is configured for:

- Roles: Data Engineer, Cloud Engineer
- Locations: Noida, Gurgaon/Gurugram
- Experience: 1 year / junior
- Remote-only filtering: off

Run it with:

```powershell
.\autoapply.cmd phase1 --preview
.\autoapply.cmd phase1 --limit 4
```

For heavier semantic matching similar to Resume-Matcher embeddings, install the optional ML extras:

```powershell
pip install -r requirements-ml.txt
```

## Configuration

Update these before real usage:

- `config/profile.yaml`: phone number, experience, location, resume path.
- `config/filters.yaml`: platforms, locations, salary, excluded companies, excluded keywords.
- `.env`: database URL, cookies path, AWS values, dry-run settings.
- `config/linkedin_cookies.json`: copy from the `.example` file and replace with exported session cookies.

## AWS Deployment

Create these SecureString parameters before running Terraform:

```bash
aws ssm put-parameter --name /autoapply/prod/db_password --type SecureString --value "replace-me"
```

Then run:

```bash
bash infra/deploy.sh --env prod
```

Terraform creates VPC, RDS PostgreSQL, S3, SQS queues, SNS email alerts, EventBridge schedules, ECR repos, image-based Lambdas, and an ECS Fargate applier service.

## AWS Low-Resource Smoke Test

To test on an existing VM without touching running services, add these to `.env`:

```dotenv
AWS_SSH_HOST=
AWS_SSH_USER=ubuntu
AWS_SSH_KEY_PATH=C:\path\to\key.pem
AWS_REMOTE_PROJECT_DIR=/tmp/autoapply-codex-test
```

Then run:

```powershell
.\scripts\aws_low_resource_smoke_test.ps1
```

This uploads a copy to `/tmp/autoapply-codex-test`, runs only Python help and syntax checks, and does not start Docker, systemd services, Terraform, or existing app processes.

For an isolated production-style test on the existing VM:

```powershell
.\scripts\aws_production_test.ps1 -Platform indeed -Limit 2
```

This deploys to `~/autoapply-prod-test`, starts only project-scoped PostgreSQL and Redis containers on localhost ports `55432` and `56379`, runs Phase 1 with dry-run applications, and leaves existing ports/services alone.

For browser-based job board testing with Playwright:

```powershell
.\scripts\aws_production_test.ps1 -BrowserRuntime -Platform naukri -Limit 2
.\scripts\aws_production_test.ps1 -BrowserRuntime -Platform linkedin -Limit 2
```

If a board blocks the scraper or returns an empty page, debug HTML and screenshots are written under `reports/debug/` in the isolated VM folder.

## Notes

- Scrapers include random delays and optional proxies through `PROXY_LIST`.
- The matcher works with pure-Python keyword scoring by default. Install `requirements-ml.txt` to add scikit-learn TF-IDF and `all-MiniLM-L6-v2` semantic scoring.
- Screening answers use free local templates from `config/screening_answers.yaml`; no paid LLM API key is required.
- The Go dashboard can be started with `.\autoapply.cmd dashboard` after Go is installed.
- Site layouts change often, so scraper selectors should be treated as maintained adapters.

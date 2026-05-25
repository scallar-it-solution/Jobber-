# Reference Project Usage

AutoApply uses the two requested GitHub projects as design references without copying paid-API assumptions into the runtime path.

## career-ops

Source: https://github.com/santifer/career-ops

Mapped ideas:

- Local-first job search command center
- Batch processing flow
- Go terminal dashboard
- Daily reporting workflow
- Human-reviewable job pipeline

AutoApply implementation points:

- `autoapply_cli.py`
- `batch/`
- `dashboard/`
- `reports/`

## Resume-Matcher

Source: https://github.com/srbhr/Resume-Matcher

Mapped ideas:

- Resume parsing
- ATS-style keyword overlap
- Semantic similarity scoring
- Missing keyword extraction
- Match score and queue threshold

AutoApply implementation points:

- `matcher/resume_parser.py`
- `matcher/scoring.py`
- `matcher/score.py`
- `matcher/batch_score.py`

## Free Tooling Policy

The project now avoids Anthropic or any other paid LLM API key by default.

Screening answers use:

- `config/profile.yaml`
- `config/screening_answers.yaml`
- deterministic local templates in `applier/llm.py`
- Codex-assisted manual review when you ask Codex to improve a specific answer

The app cannot call Codex by itself unless you explicitly run Codex in this workspace. For unknown or sensitive screening questions, paste the question into Codex and use the profile context from `config/profile.yaml`.


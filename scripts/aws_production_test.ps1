param(
  [string]$RemoteDir = "",
  [string]$Platform = "indeed",
  [int]$Limit = 2,
  [switch]$SkipInstall,
  [switch]$SkipUpload,
  [switch]$SkipScrape
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
  throw ".env not found. Add AWS_SSH_HOST, AWS_SSH_USER, and AWS_SSH_KEY_PATH."
}

$vars = @{}
Get-Content $envFile | ForEach-Object {
  if ($_ -match '^\s*([^#=\s]+)\s*=\s*(.*)\s*$') {
    $vars[$matches[1]] = $matches[2].Trim().Trim('"').Trim("'")
  }
}

$hostName = $vars["AWS_SSH_HOST"]
$userName = $vars["AWS_SSH_USER"]
$keyPath = $vars["AWS_SSH_KEY_PATH"]
if (-not $RemoteDir) {
  $RemoteDir = $vars["AWS_PROD_TEST_DIR"]
}
if (-not $RemoteDir) {
  $RemoteDir = "~/autoapply-prod-test"
}

if (-not $hostName -or -not $userName -or -not $keyPath) {
  throw "Missing AWS_SSH_HOST, AWS_SSH_USER, or AWS_SSH_KEY_PATH in .env."
}
if ($RemoteDir.StartsWith("~/")) {
  $RemoteDir = "/home/$userName/" + $RemoteDir.Substring(2)
}
if (($RemoteDir -notmatch '^/home/[^/]+/autoapply-[A-Za-z0-9._-]+$') -and ($RemoteDir -notmatch '^/tmp/autoapply-[A-Za-z0-9._-]+$')) {
  throw "Unsafe AWS_PROD_TEST_DIR: $RemoteDir"
}

$sshTarget = "$userName@$hostName"
$sshBase = @("-i", $keyPath, "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=accept-new", $sshTarget)

if (-not $SkipUpload) {
  $stage = Join-Path $env:TEMP ("autoapply-prod-stage-" + [guid]::NewGuid().ToString("N"))
  $archive = "$stage.tgz"
  New-Item -ItemType Directory -Force -Path $stage | Out-Null

  $items = @(
    "applier", "batch", "common", "config", "data", "docs", "infra",
    "matcher", "reports", "scraper", "scripts",
    "autoapply", "autoapply_cli.py", "requirements.txt", "requirements-ml.txt",
    "requirements-prod-test.txt",
    "pyproject.toml", "Dockerfile.applier", "Dockerfile.matcher",
    "Dockerfile.runtime", "Dockerfile.scraper", "docker-compose.yml", "README.md"
  )

  foreach ($item in $items) {
    $source = Join-Path $root $item
    if (Test-Path $source) {
      Copy-Item -Path $source -Destination $stage -Recurse -Force
    }
  }

  tar -czf $archive -C $stage .
  ssh @sshBase "mkdir -p '$RemoteDir'"
  scp -i "$keyPath" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new "$archive" "${sshTarget}:/tmp/autoapply-prod-test.tgz"
  ssh @sshBase "set -eu; mkdir -p $RemoteDir; find $RemoteDir -mindepth 1 -maxdepth 1 ! -name reports ! -name references -exec rm -rf {} +; tar -xzf /tmp/autoapply-prod-test.tgz -C $RemoteDir; rm -f /tmp/autoapply-prod-test.tgz"

  Remove-Item -LiteralPath $stage -Recurse -Force
  Remove-Item -LiteralPath $archive -Force
}

$installFlag = if ($SkipInstall) { "1" } else { "0" }
$scrapeFlag = if ($SkipScrape) { "1" } else { "0" }

$remoteScript = @"
set -euo pipefail
REMOTE_DIR="$RemoteDir"
case "`$REMOTE_DIR" in /home/*/autoapply-*|/tmp/autoapply-*) ;; *) echo "Unsafe remote dir: `$REMOTE_DIR"; exit 64;; esac
cd "`$REMOTE_DIR"
export DEPLOY_TARGET=aws
export APPLIER_DRY_RUN=true
export APPLIER_ANSWER_MODE=local
export DATABASE_URL='postgresql://autoapply:autoapply@127.0.0.1:55432/autoapply'
export REDIS_URL='redis://127.0.0.1:56379/0'

echo '== remote =='
hostname
whoami
python3 --version
docker --version
docker compose version

if [ '$installFlag' != '1' ]; then
  echo '== docker build runtime =='
  docker build -f Dockerfile.runtime -t autoapply-prod-test:latest . >/tmp/autoapply-docker-build.log
fi

run_app() {
  docker run --rm --network host \
    -e DEPLOY_TARGET=aws \
    -e APPLIER_DRY_RUN=true \
    -e APPLIER_ANSWER_MODE=local \
    -e PYTHONPATH=/app \
    -e DATABASE_URL="`$DATABASE_URL" \
    -e REDIS_URL="`$REDIS_URL" \
    -v "`$PWD/reports:/app/reports" \
    autoapply-prod-test:latest "`$@"
}

echo '== phase1 preview =='
run_app python -B autoapply phase1 --preview

echo '== compose up =='
docker compose -f infra/aws-test/docker-compose.yml up -d postgres redis

echo '== wait for postgres =='
for i in `$(seq 1 30); do
  if docker exec autoapply-prod-test-postgres pg_isready -U autoapply -d autoapply >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
docker exec autoapply-prod-test-postgres pg_isready -U autoapply -d autoapply

echo '== init db =='
run_app python -B autoapply init-db

if [ '$scrapeFlag' != '1' ]; then
  echo '== live scrape =='
  set +e
  run_app python -B autoapply phase1 --platform '$Platform' --limit $Limit | tee /tmp/autoapply-prod-scrape.log
  scrape_status="`${PIPESTATUS[0]}"
  set -e
  if [ "`$scrape_status" -ne 0 ]; then
    echo "Live scrape failed or was blocked with status `$scrape_status; seeding a Noida sample job for downstream production test."
    run_app python -B scripts/seed_sample_job.py
  fi
else
  echo '== seed sample job =='
  run_app python -B scripts/seed_sample_job.py
fi

echo '== match =='
run_app python -B autoapply match --limit 25 | tee /tmp/autoapply-prod-match.log

echo '== apply dry-run =='
run_app python -B autoapply apply --max-daily 5 | tee /tmp/autoapply-prod-apply.log

echo '== report =='
run_app python -B autoapply report | tee /tmp/autoapply-prod-report.log

echo '== db summary =='
docker run --rm --network host -e DATABASE_URL="`$DATABASE_URL" autoapply-prod-test:latest python - <<'PY'
import os
import psycopg
with psycopg.connect(os.environ['DATABASE_URL']) as conn:
    for label, sql in [
        ('jobs', 'select count(*) from jobs'),
        ('queued', "select count(*) from jobs where status='queued'"),
        ('applications', 'select count(*) from applications'),
        ('scraper_runs', 'select count(*) from scraper_runs'),
    ]:
        print(f"{label}={conn.execute(sql).fetchone()[0]}")
PY

echo '== done =='
"@

$localRunScript = Join-Path $env:TEMP ("autoapply-prod-run-" + [guid]::NewGuid().ToString("N") + ".sh")
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($localRunScript, ($remoteScript -replace "`r`n", "`n"), $utf8NoBom)
scp -i "$keyPath" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new "$localRunScript" "${sshTarget}:/tmp/autoapply-prod-run.sh"
Remove-Item -LiteralPath $localRunScript -Force
ssh @sshBase "bash /tmp/autoapply-prod-run.sh"
$remoteExit = $LASTEXITCODE
ssh @sshBase "rm -f /tmp/autoapply-prod-run.sh" | Out-Null
if ($remoteExit -ne 0) {
  exit $remoteExit
}

param(
  [switch]$SkipUpload
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
  throw ".env not found. Add AWS_SSH_HOST, AWS_SSH_USER, AWS_SSH_KEY_PATH, and AWS_REMOTE_PROJECT_DIR."
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
$remoteDir = $vars["AWS_REMOTE_PROJECT_DIR"]

if (-not $hostName -or -not $userName -or -not $keyPath) {
  throw "Missing AWS_SSH_HOST, AWS_SSH_USER, or AWS_SSH_KEY_PATH in .env."
}
if (-not $remoteDir) {
  $remoteDir = "/tmp/autoapply-codex-test"
}

$sshTarget = "$userName@$hostName"
$sshBase = @("-i", $keyPath, "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=accept-new", $sshTarget)

if (-not $SkipUpload) {
  $stage = Join-Path $env:TEMP ("autoapply-stage-" + [guid]::NewGuid().ToString("N"))
  $zip = "$stage.zip"
  New-Item -ItemType Directory -Force -Path $stage | Out-Null

  $items = @(
    "applier", "batch", "common", "config", "data", "docs", "infra",
    "matcher", "reports", "scraper", "scripts",
    "autoapply", "autoapply_cli.py", "requirements.txt", "pyproject.toml",
    "Dockerfile.applier", "Dockerfile.matcher", "Dockerfile.scraper",
    "docker-compose.yml", "README.md"
  )

  foreach ($item in $items) {
    $source = Join-Path $root $item
    if (Test-Path $source) {
      Copy-Item -Path $source -Destination $stage -Recurse -Force
    }
  }

  Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip -Force
  ssh @sshBase "mkdir -p '$remoteDir' && find '$remoteDir' -mindepth 1 -maxdepth 1 -exec rm -rf {} +"
  scp -i "$keyPath" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new "$zip" "${sshTarget}:/tmp/autoapply-codex-test.zip"
  ssh @sshBase "unzip -q -o /tmp/autoapply-codex-test.zip -d '$remoteDir' && rm -f /tmp/autoapply-codex-test.zip"

  Remove-Item -LiteralPath $stage -Recurse -Force
  Remove-Item -LiteralPath $zip -Force
}

$remoteScript = @"
set -eu
cd '$remoteDir'
echo 'Remote:' `$(hostname)
echo 'Project dir:' `$(pwd)
python3 --version
python3 -B autoapply --help >/tmp/autoapply-help.txt
python3 -B autoapply phase1 --preview >/tmp/autoapply-phase1-preview.txt
python3 -B -m compileall -q common scraper matcher applier batch reports infra scripts autoapply_cli.py
echo 'Smoke test passed without starting services or touching existing workloads.'
"@

ssh @sshBase $remoteScript

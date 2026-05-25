$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$referenceDir = Join-Path $root "references"
New-Item -ItemType Directory -Force -Path $referenceDir | Out-Null

$repos = @(
  @{
    Name = "career-ops"
    Url = "https://github.com/santifer/career-ops.git"
  },
  @{
    Name = "Resume-Matcher"
    Url = "https://github.com/srbhr/Resume-Matcher.git"
  }
)

foreach ($repo in $repos) {
  $target = Join-Path $referenceDir $repo.Name
  if (Test-Path $target) {
    Write-Host "$($repo.Name) already exists; fetching latest shallow history."
    git -C $target fetch --depth 1 origin
    git -C $target reset --hard origin/HEAD
  } else {
    Write-Host "Cloning $($repo.Name) with depth 1."
    git clone --depth 1 $repo.Url $target
  }
}


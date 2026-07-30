<#
  push.ps1 - the ONLY sanctioned way to push (L1, L2).

  Guarantees:
    - target repo is verified before anything is sent
    - the token is read from another repo's remote, held in memory, never written
    - `-u` is never used, so the token cannot land in .git/config
    - .git/config is re-verified clean afterwards
    - the token is masked in all output

  Usage:  pwsh tools/push.ps1 -Message "feat: thing"   # commits then pushes
          pwsh tools/push.ps1 -DryRun                  # verifies plumbing only
#>
param(
  [string]$Message = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Expected = "thirumani-vihaan/hackathon"

function Fail($m) { Write-Host "PUSH FAILED: $m" -ForegroundColor Red; exit 1 }

# --- L1: account lock ---------------------------------------------------
$origin = git -C $Repo config --get remote.origin.url
if ($origin -notmatch [regex]::Escape($Expected)) {
  Fail "remote.origin.url is '$origin', expected to contain '$Expected'"
}

# --- token: from another repo's remote, memory only ---------------------
$src = Join-Path $env:USERPROFILE "Desktop\tutor\MentorOverlay"
$srcUrl = git -C $src config --get remote.personal.url 2>$null
if (-not $srcUrl) { Fail "cannot locate credential source" }
if ($srcUrl -notmatch '://([^:@/]+)(?::([^@]+))?@') { Fail "credential source malformed" }
$tok = if ([string]::IsNullOrEmpty($matches[2])) { $matches[1] } else { $matches[2] }
function Mask($t) { if ($t) { $t -replace [regex]::Escape($tok), '***' } else { "" } }

# --- L2: secret scan is a gate, not a warning ---------------------------
if ($Message) {
  git -C $Repo add -A | Out-Null
  $scan = python "$Repo\tools\secret_scan.py" staged 2>&1 | Out-String
  Write-Host $scan.Trim()
  if ($LASTEXITCODE -ne 0) { Fail "secret scan blocked the commit" }

  $staged = git -C $Repo diff --cached --name-only
  if ($staged) {
    git -C $Repo commit -q -m $Message
    if ($LASTEXITCODE -ne 0) { Fail "commit failed" }
    Write-Host "committed: $(git -C $Repo log --oneline -1)"
  } else {
    Write-Host "nothing staged; skipping commit"
  }
}

if ($DryRun) {
  Write-Host "DRY RUN: remote ok, token resolved (len $($tok.Length)), scan path ok"
  exit 0
}

# --- push: URL inline, never -u -----------------------------------------
$url = "https://x-access-token:$tok@github.com/$Expected.git"
$out = git -C $Repo push $url main 2>&1 | Out-String
Write-Host (Mask $out).Trim()

if ($LASTEXITCODE -ne 0) {
  # Ladder step 2: rebase on origin and retry once.
  git -C $Repo fetch $url main 2>&1 | Out-Null
  git -C $Repo rebase FETCH_HEAD 2>&1 | Out-Null
  $out = git -C $Repo push $url main 2>&1 | Out-String
  Write-Host (Mask $out).Trim()
  if ($LASTEXITCODE -ne 0) { Fail "push failed after rebase retry - log to BLOCKERS.md and keep building" }
}

git -C $Repo fetch origin -q 2>&1 | Out-Null

# --- L2: verify no token landed in .git/config --------------------------
if (Select-String -Path "$Repo\.git\config" -Pattern 'ghp_|github_pat|x-access-token' -Quiet) {
  Fail "TOKEN LEAKED INTO .git/config - HARD STOP"
}
Write-Host "push ok; .git/config clean"

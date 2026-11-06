[CmdletBinding()]
param(
    [switch]$Build,
    [switch]$Record
)

# E1 acceptance: session contract -> real Docker execution -> V-23/V-24.
# Recording opens a mintty window and captures it with gdigrab; use -Record
# only on an interactive desktop.

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$spec = "CourseControl/tests/fixtures/lesson-smoke/sessions/shell-001.session.json"
$lessonDir = "CourseControl/tests/fixtures/lesson-smoke"

Push-Location $root
try {
    $imageOk = $false
    & docker image inspect course-tools:e1 *> $null
    if ($LASTEXITCODE -eq 0) { $imageOk = $true }
    if ($Build -or -not $imageOk) {
        & (Join-Path $PSScriptRoot "build-session-image.ps1")
        if ($LASTEXITCODE -ne 0) {
            Write-Host "session check failed: image build"
            exit 1
        }
    }

    Write-Host "validate session"
    uv run --project CourseControl course-control session-validate `
        --spec $spec --lesson-dir $lessonDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "session check failed: validate"
        exit 1
    }

    Write-Host "run session"
    $recordArg = if ($Record) { "--record" } else { "--no-record" }
    uv run --project CourseControl course-control session-run `
        --spec $spec --lesson-dir $lessonDir --workspace . $recordArg
    if ($LASTEXITCODE -ne 0) {
        Write-Host "session check failed: run"
        exit 1
    }

    Write-Host "session check ok"
    exit 0
}
finally {
    Pop-Location
}

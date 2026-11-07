[CmdletBinding()]
param(
    [switch]$Record
)

# E3 acceptance: venv + local wheel install + offline verification (V-25).
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$spec = "CourseControl/tests/fixtures/lesson-smoke/sessions/python-001.session.json"
$lessonDir = "CourseControl/tests/fixtures/lesson-smoke"

Push-Location $root
try {
    Write-Host "validate python session"
    uv run --project CourseControl course-control session-validate `
        --spec $spec --lesson-dir $lessonDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "python session check failed: validate"
        exit 1
    }

    Write-Host "run python session"
    $recordArg = if ($Record) { "--record" } else { "--no-record" }
    uv run --project CourseControl course-control session-run `
        --spec $spec --lesson-dir $lessonDir --workspace . $recordArg
    if ($LASTEXITCODE -ne 0) {
        Write-Host "python session check failed: run"
        exit 1
    }

    Write-Host "python session check ok"
    exit 0
}
finally {
    Pop-Location
}

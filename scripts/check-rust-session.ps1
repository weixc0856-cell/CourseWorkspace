[CmdletBinding()]
param(
    [switch]$Record
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$spec = "CourseControl/tests/fixtures/lesson-smoke/sessions/rust-001.session.json"
$lessonDir = "CourseControl/tests/fixtures/lesson-smoke"

Push-Location $root
try {
    uv run --project CourseControl course-control session-validate `
        --spec $spec --lesson-dir $lessonDir
    if ($LASTEXITCODE -ne 0) { Write-Host "rust session check failed: validate"; exit 1 }
    $recordArg = if ($Record) { "--record" } else { "--no-record" }
    uv run --project CourseControl course-control session-run `
        --spec $spec --lesson-dir $lessonDir --workspace . $recordArg
    if ($LASTEXITCODE -ne 0) { Write-Host "rust session check failed: run"; exit 1 }
    Write-Host "rust session check ok"
    exit 0
}
finally {
    Pop-Location
}

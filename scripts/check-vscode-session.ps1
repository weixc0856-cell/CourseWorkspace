[CmdletBinding()]
param(
    [switch]$Record
)

# E2 acceptance: real VS Code window + shell integration + optional recording.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$spec = "CourseControl/tests/fixtures/lesson-smoke/sessions/vscode-001.session.json"
$lessonDir = "CourseControl/tests/fixtures/lesson-smoke"

Push-Location $root
try {
    Write-Host "validate vscode session"
    uv run --project CourseControl course-control session-validate `
        --spec $spec --lesson-dir $lessonDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "vscode session check failed: validate"
        exit 1
    }

    Write-Host "run vscode session"
    $recordArg = if ($Record) { "--record" } else { "--no-record" }
    uv run --project CourseControl course-control session-run `
        --spec $spec --lesson-dir $lessonDir --workspace . $recordArg
    if ($LASTEXITCODE -ne 0) {
        Write-Host "vscode session check failed: run"
        exit 1
    }

    Write-Host "vscode session check ok"
    exit 0
}
finally {
    Pop-Location
}

[CmdletBinding()]
param(
    [switch]$Record
)

# E3 network path: install from a host-local HTTP index, then verify offline.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$spec = "CourseControl/tests/fixtures/lesson-smoke/sessions/python-network-001.session.json"
$lessonDir = "CourseControl/tests/fixtures/lesson-smoke"
$wheels = Join-Path $root "CourseControl/tests/fixtures/lesson-smoke/assets/code/python-001/wheels"

Push-Location $root
try {
    $server = Start-Process python -ArgumentList "-m","http.server","8899","--bind","0.0.0.0","--directory",$wheels -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 1
    try {
        uv run --project CourseControl course-control session-validate `
            --spec $spec --lesson-dir $lessonDir
        if ($LASTEXITCODE -ne 0) { Write-Host "python network check failed: validate"; exit 1 }
        $recordArg = if ($Record) { "--record" } else { "--no-record" }
        uv run --project CourseControl course-control session-run `
            --spec $spec --lesson-dir $lessonDir --workspace . $recordArg
        if ($LASTEXITCODE -ne 0) { Write-Host "python network check failed: run"; exit 1 }
    }
    finally {
        if ($script:server) { Stop-Process -Id $script:server.Id -Force -ErrorAction SilentlyContinue }
        if ($server) { Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue }
    }
    Write-Host "python network check ok"
    exit 0
}
finally {
    Pop-Location
}

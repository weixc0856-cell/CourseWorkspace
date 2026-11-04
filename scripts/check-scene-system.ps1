[CmdletBinding()]
param(
    [switch]$Render
)

# See scripts/check.ps1: native stderr must not abort the script under
# PowerShell 5.1, and expected failures must be inverted explicitly.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$script:failed = $false

function Invoke-Checked {
    param([string]$Label, [scriptblock]$Action)
    Write-Host $Label
    & $Action
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $Label (exit $LASTEXITCODE)"
        $script:failed = $true
    }
}

function Expect-Failure {
    param([string]$Label, [scriptblock]$Action)
    Write-Host $Label
    & $Action
    if ($LASTEXITCODE -eq 0) {
        Write-Host "FAILED: $Label (expected rejection, got exit 0)"
        $script:failed = $true
    }
}

Push-Location $root
try {
    $valid = @(
        "demo-scene",
        "demo-animation",
        "demo-geometry-nodes",
        "demo-animation-scene",
        "demo-modify",
        "demo-text-curve",
        "demo-materials"
    )
    $invalid = @(
        "invalid-collection-root",
        "invalid-duplicate-id",
        "invalid-material-ref",
        "invalid-no-camera",
        "invalid-output-outside",
        "invalid-primitive",
        "invalid-text-empty",
        "invalid-text-primitive",
        "invalid-curve-points",
        "invalid-curve-bevel",
        "invalid-camera-projection"
    )

    foreach ($name in $valid) {
        Invoke-Checked "validate $name" {
            uv run --project CourseControl course-control scene-validate `
                --task "BlenderStudio/tasks/scene-system/$name.json" --workspace .
        }
    }

    foreach ($name in $invalid) {
        Expect-Failure "expect reject $name" {
            uv run --project CourseControl course-control scene-validate `
                --task "BlenderStudio/tasks/scene-system/$name.json" --workspace . `
                2>&1 | Out-Null
        }
    }

    if ($Render -and -not $script:failed) {
        foreach ($name in @("demo-scene", "demo-geometry-nodes", "demo-animation-scene", "demo-modify", "demo-text-curve", "demo-materials")) {
            Invoke-Checked "render $name" {
                uv run --project CourseControl course-control scene-run `
                    --task "BlenderStudio/tasks/scene-system/$name.json" --workspace .
            }
        }
    }

    if ($script:failed) {
        Write-Host "scene system check failed"
        exit 1
    }
    Write-Host "scene system check ok"
    exit 0
}
finally {
    Pop-Location
}

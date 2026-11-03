[CmdletBinding()]
param()

# Native commands (uv) write progress to stderr. With ErrorActionPreference=Stop,
# PowerShell 5.1 turns that into NativeCommandError and aborts the script, so the
# checks below run with Continue and inspect $LASTEXITCODE explicitly.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$script:failed = $false

function Invoke-Checked {
    param([string]$Label, [scriptblock]$Action, [switch]$Quiet)
    Write-Host $Label
    if ($Quiet) {
        $output = & $Action 2>&1
        $code = $LASTEXITCODE
        if ($code -ne 0) {
            $output | ForEach-Object { Write-Host $_ }
            Write-Host "FAILED: $Label (exit $code)"
            $script:failed = $true
        }
    }
    else {
        & $Action
        if ($LASTEXITCODE -ne 0) {
            Write-Host "FAILED: $Label (exit $LASTEXITCODE)"
            $script:failed = $true
        }
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
    Invoke-Checked "fixtures" { & (Join-Path $PSScriptRoot "prepare-fixtures.ps1") }

    Invoke-Checked "toolchain" {
        uv run --project CourseControl course-control audit --workspace .
    }

    Invoke-Checked "unit tests: CourseControl" -Quiet {
        uv run --project CourseControl python -m unittest discover `
            -s CourseControl/tests -t CourseControl
    }
    Invoke-Checked "unit tests: ModelingStudio" -Quiet {
        uv run --project ModelingStudio python -m unittest discover `
            -s ModelingStudio/tests -t ModelingStudio
    }
    Invoke-Checked "unit tests: ai_runtime" -Quiet {
        uv run --project shared/ai_runtime python -m unittest discover `
            -s shared/ai_runtime/tests -t shared/ai_runtime
    }
    Invoke-Checked "unit tests: ContentQA" -Quiet {
        uv run --project ContentQA python -m unittest discover `
            -s ContentQA/tests -t ContentQA
    }

    $lessons = @(
        @{Lesson = "01-shell-for-ai-era"; Dir = "lessons"},
        @{Lesson = "01-transformer-demo"; Dir = "lessons"},
        @{Lesson = "lesson-smoke"; Dir = "CourseControl/tests/fixtures"},
        @{Lesson = "lesson-blender-only"; Dir = "CourseControl/tests/fixtures"},
        @{Lesson = "lesson-manual"; Dir = "CourseControl/tests/fixtures"}
    )
    foreach ($lesson in $lessons) {
        $name = $lesson.Lesson
        if (-not (Test-Path (Join-Path $lesson.Dir $name))) {
            Write-Host "skip validate $name (local content not present)"
            continue
        }
        Invoke-Checked "validate $name" {
            uv run --project CourseControl course-control validate `
                --lesson $name --lesson-dir $lesson.Dir --workspace .
        }
    }

    $validTasks = @(
        "demo-scene",
        "demo-animation",
        "demo-geometry-nodes",
        "demo-animation-scene",
        "demo-modify"
    )
    foreach ($name in $validTasks) {
        Invoke-Checked "scene-validate $name" {
            uv run --project CourseControl course-control scene-validate `
                --task "BlenderStudio/tasks/scene-system/$name.json" --workspace . `
                2>&1 | Out-Null
        }
    }

    $invalidTasks = @(
        "invalid-collection-root",
        "invalid-duplicate-id",
        "invalid-material-ref",
        "invalid-no-camera",
        "invalid-output-outside",
        "invalid-primitive"
    )
    foreach ($name in $invalidTasks) {
        Expect-Failure "scene-validate $name (must be rejected)" {
            uv run --project CourseControl course-control scene-validate `
                --task "BlenderStudio/tasks/scene-system/$name.json" --workspace . `
                2>&1 | Out-Null
        }
    }

    if ($script:failed) {
        Write-Host "check failed"
        exit 1
    }
    Write-Host "check ok"
    exit 0
}
finally {
    Pop-Location
}

[CmdletBinding()]
param([switch]$CleanClone, [switch]$SkipUnitTests)

# Native commands (uv) write progress to stderr. With ErrorActionPreference=Stop,
# PowerShell 5.1 turns that into NativeCommandError and aborts the script, so the
# checks below run with Continue and inspect $LASTEXITCODE explicitly.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "_layout.ps1")
$content = Get-ContentRoot -Workspace $root
$script:failed = $false

function Invoke-Checked {
    param([string]$Label, [scriptblock]$Action, [switch]$Quiet)
    Write-Host $Label
    if ($Quiet) {
        $output = (& $Action 2>&1 | Out-String)
        $code = $LASTEXITCODE
        if ($code -ne 0) {
            Write-Host $output
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

    Invoke-Checked "path hygiene" {
        & (Join-Path $PSScriptRoot "check-paths.ps1")
    }

    # Missing evidence is allowed only when every path has a recorded
    # disposition in docs/audit/evidence-decisions.yaml. A clean clone has no
    # build outputs, so this check is local-only.
    if ($CleanClone) {
        Write-Host "skip evidence paths (clean clone: build outputs are not present)"
    }
    else {
        Invoke-Checked "evidence paths" -Quiet {
            uv run --project CourseControl python scripts/check_evidence.py --workspace .
        }
    }

    Invoke-Checked "vendor three.js" -Quiet {
        uv run --project CourseControl course-control vendor-check --workspace .
    }

    Invoke-Checked "shot taxonomy" -Quiet {
        uv run --project CourseControl course-control shot-taxonomy --workspace . 2>&1 | Out-Null
    }

    if ($CleanClone -and -not (Test-Path "BlenderStudio/scenes/01-transformer-demo")) {
        Write-Host "skip blender task 01-transformer-demo (local scene not present)"
    }
    else {
        Invoke-Checked "blender task 01-transformer-demo" -Quiet {
            uv run --project CourseControl course-control blender-task-validate `
                --task BlenderStudio/tasks/01-transformer-demo/stack_explode.json --workspace . 2>&1 | Out-Null
        }
    }

    if ($SkipUnitTests) {
        Write-Host "skip unit tests (run separately)"
    }
    else {
        Invoke-Checked "unit tests: CourseControl" {
            uv run --project CourseControl python -m unittest discover `
                -s CourseControl/tests -t CourseControl
        }
        Invoke-Checked "unit tests: ModelingStudio" {
            uv run --project ModelingStudio python -m unittest discover `
                -s ModelingStudio/tests -t ModelingStudio
        }
        Invoke-Checked "unit tests: ai_runtime" {
            uv run --project shared/ai_runtime python -m unittest discover `
                -s shared/ai_runtime/tests -t shared/ai_runtime
        }
        Invoke-Checked "unit tests: ContentQA" {
            uv run --project ContentQA python -m unittest discover `
                -s ContentQA/tests -t ContentQA
        }
        Invoke-Checked "unit tests: ManimSandbox" {
            uv run --project ManimSandbox python -m unittest discover `
                -s ManimSandbox/tests -t ManimSandbox
        }
        Invoke-Checked "unit tests: KnowledgeStudio" {
            uv run --project KnowledgeStudio python -m unittest discover `
                -s KnowledgeStudio/tests -t KnowledgeStudio
        }
    }
    Invoke-Checked "remotion typecheck" -Quiet {
        & (Join-Path $root "RemotionStudio/node_modules/.bin/tsc.cmd") `
            --noEmit -p (Join-Path $root "RemotionStudio/tsconfig.json")
    }

    $lessons = @(
        @{Lesson = "01-shell-for-ai-era"; Dir = (Join-Path $content "lessons")},
        @{Lesson = "01-transformer-demo"; Dir = (Join-Path $content "lessons")},
        @{Lesson = "lesson-smoke"; Dir = "CourseControl/tests/fixtures"},
        @{Lesson = "lesson-blender-only"; Dir = "CourseControl/tests/fixtures"},
        @{Lesson = "lesson-manual"; Dir = "CourseControl/tests/fixtures"}
        @{Lesson = "lesson-authoring"; Dir = "CourseControl/tests/fixtures"}
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

    if (Test-Path (Join-Path $content "lessons/01-transformer-demo")) {
        Invoke-Checked "director plan 01-transformer-demo" {
            uv run --project CourseControl course-control director-plan `
                --lesson 01-transformer-demo --workspace . `
                --out (Join-Path $content "build/01-transformer-demo/director") 2>&1 | Out-Null
        }
    }

    $validTasks = @(
        "demo-scene",
        "demo-animation",
        "demo-geometry-nodes",
        "demo-animation-scene",
        "demo-modify",
        "demo-text-curve",
        "demo-materials",
        "demo-scientific",
        "demo-surface"
    )
    foreach ($name in $validTasks) {
        Invoke-Checked "scene-validate $name" {
            uv run --project CourseControl course-control scene-validate `
                --task "BlenderStudio/tasks/scene-system/$name.json" --workspace . `
                2>&1 | Out-Null
        }
    }

    Invoke-Checked "session-validate shell-001" {
        uv run --project CourseControl course-control session-validate `
            --spec CourseControl/tests/fixtures/lesson-smoke/sessions/shell-001.session.json `
            --lesson-dir CourseControl/tests/fixtures/lesson-smoke
    }

    Invoke-Checked "session-validate vscode-001" {
        uv run --project CourseControl course-control session-validate `
            --spec CourseControl/tests/fixtures/lesson-smoke/sessions/vscode-001.session.json `
            --lesson-dir CourseControl/tests/fixtures/lesson-smoke
    }

    Invoke-Checked "session-validate rust-001" {
        uv run --project CourseControl course-control session-validate `
            --spec CourseControl/tests/fixtures/lesson-smoke/sessions/rust-001.session.json `
            --lesson-dir CourseControl/tests/fixtures/lesson-smoke
    }

    Invoke-Checked "session-validate python-network-001" {
        uv run --project CourseControl course-control session-validate `
            --spec CourseControl/tests/fixtures/lesson-smoke/sessions/python-network-001.session.json `
            --lesson-dir CourseControl/tests/fixtures/lesson-smoke
    }

    Invoke-Checked "session-validate python-001" {
        uv run --project CourseControl course-control session-validate `
            --spec CourseControl/tests/fixtures/lesson-smoke/sessions/python-001.session.json `
            --lesson-dir CourseControl/tests/fixtures/lesson-smoke
    }

    $invalidTasks = @(
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

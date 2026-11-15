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

# One full regression per workspace. Two sessions sharing the workspace must not
# run check.ps1 at the same time: they would race for ports and temp files and
# the green result would be untrustworthy. The lock lives in the content root
# with the other runtime state, never in the repository.
function Get-RegressionLock {
    param([string]$Root, [string]$Content)
    $sha1 = [System.Security.Cryptography.SHA1]::Create()
    try {
        $digest = [System.BitConverter]::ToString(
            $sha1.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Root.ToLowerInvariant()))
        ).Replace("-", "").Substring(0, 8).ToLowerInvariant()
    }
    finally {
        $sha1.Dispose()
    }
    $dir = Join-Path $Content "runtime\locks"
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $path = Join-Path $dir ("check.{0}.lock" -f $digest)
    if (Test-Path -LiteralPath $path) {
        $info = $null
        try { $info = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json } catch { $info = $null }
        $started = $null
        if ($info -and $info.started) {
            try {
                $started = [datetime]::Parse(
                    $info.started,
                    [Globalization.CultureInfo]::InvariantCulture,
                    [Globalization.DateTimeStyles]::RoundtripKind
                )
            }
            catch { $started = $null }
        }
        $ageMinutes = if ($started) {
            ((Get-Date).ToUniversalTime() - $started.ToUniversalTime()).TotalMinutes
        }
        else { 999 }
        if ($ageMinutes -le 30) {
            $holder = if ($info -and $info.pid) { $info.pid } else { "unknown" }
            $when = if ($info -and $info.started) { $info.started } else { "unknown" }
            Write-Host "FAILED: full regression already running (pid $holder, started $when)"
            Write-Host "lock: $path"
            Write-Host "a stale lock may be taken over after 30 minutes"
            return $null
        }
        Write-Host "WARNING: taking over a stale regression lock (pid $($info.pid), started $($info.started))"
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    }
    $record = [ordered]@{
        pid = $PID
        started = (Get-Date).ToUniversalTime().ToString("o")
        workspace = $Root
    }
    try {
        $stream = [System.IO.File]::Open(
            $path,
            [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::None
        )
    }
    catch {
        Write-Host "FAILED: could not take the regression lock: $path"
        return $null
    }
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes(($record | ConvertTo-Json -Compress))
        $stream.Write($bytes, 0, $bytes.Length)
    }
    finally {
        $stream.Close()
    }
    return $path
}

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

$lock = Get-RegressionLock -Root $root -Content $content
if (-not $lock) {
    exit 1
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

    # Course media belongs in the content root. The audit walks the disk, not
    # git: an ignored file is still a file sitting in the repository.
    Invoke-Checked "content separation" {
        uv run --project CourseControl course-control separation --workspace .
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

    # Local content is surveyed, not gated: a course issue must not fail the
    # program regression, and the tracked script must not name a course.
    $localLessons = @()
    if (Test-Path (Join-Path $content "lessons")) {
        $localLessons = @(Get-ChildItem (Join-Path $content "lessons") -Directory |
            Where-Object { Test-Path (Join-Path $_.FullName "lesson.yaml") })
    }
    if ($localLessons.Count -eq 0) {
        Write-Host "skip local lesson survey (no lessons in the content root)"
    }
    else {
        Write-Host "local lesson survey (content is reported, not gated):"
        foreach ($lesson in $localLessons) {
            $survey = & uv run --project CourseControl course-control validate --lesson $lesson.Name --workspace . 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  pass $($lesson.Name)"
            }
            else {
                Write-Host "  issues $($lesson.Name)"
                $survey | Select-Object -Last 3 | ForEach-Object { Write-Host "    $_" }
            }
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
    if ($lock -and (Test-Path -LiteralPath $lock)) {
        Remove-Item -LiteralPath $lock -Force -ErrorAction SilentlyContinue
    }
}

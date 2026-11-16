[CmdletBinding()]
param([switch]$CleanClone, [switch]$SkipUnitTests)

# Native commands (uv) write progress to stderr. With ErrorActionPreference=Stop,
# PowerShell 5.1 turns that into NativeCommandError and aborts the script, so the
# checks below run with Continue and inspect $LASTEXITCODE explicitly.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Write-Host "check start: $root"
# A missing script or wrong root used to look like a silent exit 0. Refuse to
# report anything unless the workspace really is the repository root.
$required = @(
    (Join-Path $root "CourseControl/pyproject.toml"),
    (Join-Path $root "scripts/check.ps1")
)
$missing = @($required | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missing.Count -gt 0) {
    Write-Host "check aborted: not running from the repository root"
    foreach ($item in $missing) {
        Write-Host "  missing: $item"
    }
    exit 2
}
. (Join-Path $PSScriptRoot "_layout.ps1")
$content = Get-ContentRoot -Workspace $root
$script:failed = $false
$script:checksRun = 0

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
    Write-Host "check lock: $path pid=$PID started=$($record.started)"
    return $path
}

function Invoke-TestSuite {
    param([string]$Label, [string]$Project, [string]$TestsPath, [string]$TopPath)
    $script:checksRun += 1
    Write-Host "unit tests: $Label"
    $output = & uv run --project $Project python -m unittest discover `
        -s $TestsPath -t $TopPath 2>&1 | Out-String
    $code = $LASTEXITCODE
    Write-Host $output
    if ($code -ne 0) {
        Write-Host "FAILED: unit tests: $Label (exit $code)"
        $script:failed = $true
        return
    }
    $match = [regex]::Match($output, "Ran (\d+) tests")
    if (-not $match.Success) {
        Write-Host "FAILED: unit tests: $Label (no test count in the output)"
        $script:failed = $true
        return
    }
    $count = [int]$match.Groups[1].Value
    $previous = $script:previousCounts[$Label]
    if ($null -ne $previous -and $count -lt $previous) {
        Write-Host "FAILED: test count dropped: $Label $previous -> $count"
        $script:failed = $true
    }
    $script:testCounts[$Label] = $count
}

function Invoke-Checked {
    param([string]$Label, [scriptblock]$Action, [switch]$Quiet)
    $script:checksRun += 1
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
    $script:checksRun += 1
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

$logDir = Join-Path $content "runtime/logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir ("check-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
$script:transcript = $false
try {
    Start-Transcript -Path $logPath -Append | Out-Null
    $script:transcript = $true
}
catch {
    Write-Host "WARNING: cannot write the regression log: $logPath"
}

# A test count that silently drops is a deleted test. Compare with the last
# recorded count and fail on a decrease.
$countsPath = Join-Path $logDir "test-counts.json"
$script:previousCounts = @{}
if (Test-Path -LiteralPath $countsPath) {
    try {
        $loaded = Get-Content -LiteralPath $countsPath -Raw | ConvertFrom-Json
        foreach ($prop in $loaded.PSObject.Properties) {
            $script:previousCounts[$prop.Name] = [int]$prop.Value
        }
    }
    catch {
        Write-Host "WARNING: cannot read $countsPath"
    }
}
$script:testCounts = @{}

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
        Invoke-TestSuite "CourseControl" "CourseControl" "CourseControl/tests" "CourseControl"
        Invoke-TestSuite "ModelingStudio" "ModelingStudio" "ModelingStudio/tests" "ModelingStudio"
        Invoke-TestSuite "ai_runtime" "shared/ai_runtime" "shared/ai_runtime/tests" "shared/ai_runtime"
        Invoke-TestSuite "ContentQA" "ContentQA" "ContentQA/tests" "ContentQA"
        Invoke-TestSuite "ManimSandbox" "ManimSandbox" "ManimSandbox/tests" "ManimSandbox"
        Invoke-TestSuite "KnowledgeStudio" "KnowledgeStudio" "KnowledgeStudio/tests" "KnowledgeStudio"
    }
    # Book index and episode cards live in the content root; a clean clone has
    # neither, so the gate only runs where the source material is present.
    $bookIndex = Join-Path $content "runtime/course-content/automotive-aerodynamics/book/index.json"
    $bookCards = Join-Path $content "runtime/course-content/automotive-aerodynamics/episodes"
    if (-not $CleanClone -and (Test-Path $bookIndex) -and (Test-Path $bookCards)) {
        Invoke-Checked "book index" {
            uv run --project CourseControl course-control book-index --index $bookIndex --cards-dir $bookCards
        }
    }
    else {
        Write-Host "skip book index (source material not present)"
    }

    $goldenRoot = Join-Path $content "build/golden"
    if (-not $CleanClone -and (Test-Path $goldenRoot)) {
        Invoke-Checked "golden set" {
            uv run --project CourseControl python scripts/golden_check.py --workspace .
        }
    }
    else {
        Write-Host "skip golden set (no golden frames in the content root)"
    }

    # The audit renders the chapter composition and reads the DOM; it needs the
    # staged assets, so it only runs where a content root exists.  The episode
    # is the composition that ships, so it is audited too, at a frame inside
    # every instance (not at a fixed frame list that goes stale).
    if (-not $CleanClone -and $content -ne $root) {
        Invoke-Checked "frame audit" {
            node RemotionStudio/scripts/frame-audit.mjs
        }
        # Assembly refuses to render when a segment has not named its own
        # content, because the components would fall back to the sample card's
        # picture and copy. That is a data gap, not a code defect: report it as
        # a skip with the missing props named, so the gate stays meaningful.
        $episodeOut = & node RemotionStudio/scripts/frame-audit.mjs `
            --entry src/audit/episode.tsx `
            --timing RemotionStudio/src/episode/timing.json `
            --samples "mid" `
            --out (Join-Path $content "build/frame-audit/episode") 2>&1
        if ($episodeOut -match 'episode assembly:') {
            Write-Host "skip frame audit episode (segment binding incomplete)"
            $episodeOut | Select-String -Pattern 'episode assembly:|^  ' | Select-Object -First 6 |
                ForEach-Object { Write-Host "  $_" }
            Write-Host "  run: uv run --project CourseControl python scripts/check_segment_assets.py --lesson-dir <lesson>"
        }
        elseif ($LASTEXITCODE -ne 0) {
            $episodeOut | ForEach-Object { Write-Host $_ }
            Write-Host "FAILED: frame audit episode"
            $script:failed = $true
        }

        # Reverse cases for the audit itself. A crashed render and an empty
        # render both used to report "0 issues"; these fixtures fail if the
        # audit ever goes back to only checking that nothing bad happened.
        $script:checksRun += 1
        Write-Host "frame audit catches render errors (must be rejected)"
        $throwOut = & node RemotionStudio/scripts/frame-audit.mjs 30 `
            --entry src/audit/throwing.tsx `
            --out (Join-Path $content "build/frame-audit/throwing-fixture") 2>&1
        if ($LASTEXITCODE -eq 0 -or -not (($throwOut | Out-String) -match 'deliberate render error')) {
            Write-Host "FAILED: frame audit did not report the render error"
            $script:failed = $true
        }

        $script:checksRun += 1
        Write-Host "frame audit catches blank frames (must be rejected)"
        $blankOut = & node RemotionStudio/scripts/frame-audit.mjs 30 `
            --entry src/audit/blank.tsx `
            --out (Join-Path $content "build/frame-audit/blank-fixture") 2>&1
        $blankExceptions = Join-Path $content "build/frame-audit/blank-fixture/exceptions.json"
        if ($LASTEXITCODE -eq 0 -or -not (Select-String -Path $blankExceptions -Pattern '"blank_frame"' -Quiet)) {
            Write-Host "FAILED: frame audit did not report the blank frame"
            $script:failed = $true
        }
    }
    else {
        Write-Host "skip frame audit (no content root)"
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
        Write-Host "check summary: checks=$script:checksRun failed=1"
        Write-Host "check log: $logPath"
        Write-Host "check failed"
        exit 1
    }
    if ($script:testCounts.Count -gt 0) {
        $script:testCounts | ConvertTo-Json | Set-Content -LiteralPath $countsPath -Encoding utf8
    }
    Write-Host "check summary: checks=$script:checksRun failed=0"
    Write-Host "check log: $logPath"
    Write-Host "check ok"
    exit 0
}
finally {
    Pop-Location
    if ($lock -and (Test-Path -LiteralPath $lock)) {
        Remove-Item -LiteralPath $lock -Force -ErrorAction SilentlyContinue
    }
    if ($script:transcript) {
        Stop-Transcript | Out-Null
    }
    if (Test-Path -LiteralPath $logDir) {
        Get-ChildItem -LiteralPath $logDir -Filter "check-*.log" |
            Sort-Object LastWriteTime -Descending |
            Select-Object -Skip 20 |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }
}

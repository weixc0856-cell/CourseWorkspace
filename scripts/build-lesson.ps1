[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Lesson,
    [string]$LessonDir = "",
    [switch]$SkipRender,
    [switch]$SkipCompose,
    [switch]$Resume,
    [string]$ResumeFrom = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$args = @(
    "run",
    "--project", (Join-Path $root "CourseControl"),
    "course-control", "build",
    "--lesson", $Lesson,
    "--workspace", $root
)
if ($LessonDir) { $args += @("--lesson-dir", $LessonDir) }
if ($SkipRender) { $args += "--skip-render" }
if ($SkipCompose) { $args += "--skip-compose" }
if ($Resume) { $args += "--resume" }
if ($ResumeFrom) { $args += @("--resume-from", $ResumeFrom) }

Push-Location $root
try {
    & uv @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}

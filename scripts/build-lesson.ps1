[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Lesson,
    [string]$LessonDir = "lessons",
    [switch]$SkipRender,
    [switch]$SkipCompose
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$args = @(
    "run",
    "--project", (Join-Path $root "CourseControl"),
    "course-control", "build",
    "--lesson", $Lesson,
    "--lesson-dir", $LessonDir,
    "--workspace", $root
)
if ($SkipRender) { $args += "--skip-render" }
if ($SkipCompose) { $args += "--skip-compose" }

Push-Location $root
try {
    & uv @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}

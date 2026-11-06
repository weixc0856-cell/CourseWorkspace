[CmdletBinding()]
param(
    [string]$Tag = "course-tools:e1"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dockerfile = Join-Path $root "CourseControl/docker/course-tools.Dockerfile"

if (-not (Test-Path -LiteralPath $dockerfile)) {
    throw "Dockerfile not found: $dockerfile"
}

Write-Host "building $Tag from $dockerfile"
& docker build -f $dockerfile -t $Tag (Split-Path -Parent $dockerfile)
if ($LASTEXITCODE -ne 0) {
    throw "docker build failed with exit code $LASTEXITCODE"
}

$id = (& docker image inspect $Tag --format "{{.Id}}").Trim()
if ($LASTEXITCODE -ne 0 -or -not $id) {
    throw "image inspect failed for $Tag"
}
Write-Host "image: $Tag"
Write-Host "id:    $id"

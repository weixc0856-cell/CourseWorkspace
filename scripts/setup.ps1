[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "_layout.ps1")

$configPath = Join-Path $root "config/tools.yaml"
$examplePath = Join-Path $root "config/tools.example.yaml"
if (-not (Test-Path -LiteralPath $configPath)) {
    $blender = $env:BLENDER_EXE
    if (-not $blender) {
        $foundation = Join-Path $env:ProgramFiles "Blender Foundation"
        if (Test-Path -LiteralPath $foundation) {
            $candidates = Get-ChildItem -LiteralPath $foundation -Directory | Sort-Object Name -Descending
            foreach ($dir in $candidates) {
                $candidate = Join-Path $dir.FullName "blender.exe"
                if (Test-Path -LiteralPath $candidate) { $blender = $candidate; break }
            }
        }
    }
    if (-not $blender) {
        throw "Blender not found. Set BLENDER_EXE or create config/tools.yaml from config/tools.example.yaml."
    }
    $content = (Get-Content -LiteralPath $examplePath -Raw).Replace("<BLENDER_EXE>", ($blender.Replace('\', '/')))
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($configPath, $content, $utf8)
    Write-Host "created config/tools.yaml"
}

Push-Location (Join-Path $root "CourseControl")
try {
    uv sync
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }
}
finally {
    Pop-Location
}

foreach ($project in @("CourseSlides", "MotionStudio", "RemotionStudio")) {
    $dir = Join-Path $root $project
    if (-not (Test-Path (Join-Path $dir "node_modules"))) {
        Push-Location $dir
        try {
            npm ci
            if ($LASTEXITCODE -ne 0) { throw "npm ci failed in $project" }
        }
        finally {
            Pop-Location
        }
    }
}

# CodeVideo shots reuse RemotionStudio's Playwright. A junction keeps one
# install while the capture server still serves each shot directory.
$remotionModules = Join-Path $root "RemotionStudio/node_modules"
$content = Get-ContentRoot -Workspace $root
$shotsRoot = Join-Path $content "engines/code_video/shots"
if (-not (Test-Path $shotsRoot)) { $shotsRoot = Join-Path $root "CodeVideoStudio/shots" }
if ((Test-Path $shotsRoot) -and (Test-Path $remotionModules)) {
    foreach ($shot in Get-ChildItem $shotsRoot -Directory) {
        if (-not (Test-Path (Join-Path $shot.FullName "index.html"))) { continue }
        $link = Join-Path $shot.FullName "node_modules"
        if (-not (Test-Path $link)) {
            New-Item -ItemType Junction -Path $link -Target $remotionModules | Out-Null
        }
    }
}

Push-Location $root
try {
    & uv run --project CourseControl course-control vendor-sync --workspace $root | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "vendor-sync failed" }
}
finally {
    Pop-Location
}

Write-Host "setup ok"

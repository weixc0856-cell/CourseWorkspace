[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function New-FixtureVideo {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][int]$Seconds
    )
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path) | Out-Null
    ffmpeg -v error -f lavfi -i "testsrc2=size=1920x1080:rate=30" -t $Seconds `
        -c:v libx264 -pix_fmt yuv420p -y $Path
    if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed for $Path" }
}

foreach ($slug in @("lesson-smoke", "lesson-blender-only", "lesson-manual")) {
    New-FixtureVideo -Path (Join-Path $root "build/$slug/slides/recording.mp4") -Seconds 6
}

$narration = Join-Path $root "build/lesson-smoke/narration/narration.wav"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $narration) | Out-Null
ffmpeg -v error -f lavfi -i "sine=frequency=440:sample_rate=48000" -t 6 -y $narration
if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed for $narration" }

New-FixtureVideo -Path (Join-Path $root "build/lesson-manual/animation/gui_vs_cli_paths.mp4") -Seconds 1

Write-Host "fixture inputs ready"

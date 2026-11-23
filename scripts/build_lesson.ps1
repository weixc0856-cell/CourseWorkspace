<#
.SYNOPSIS
    Standardized Course Lesson Build Pipeline (Dual-Root Physical Separation Compliant)
.DESCRIPTION
    Builds a lesson's video deliverables completely inside D:\CourseContent.
    Never produces temporary artifacts, media files, or SQLite databases inside CourseWorkspace.
.PARAMETER Lesson
    The lesson slug, e.g. "t1-01-why-aerodynamics".
.PARAMETER SkipCapture
    Skip Playwright slide snapshotting.
.PARAMETER SkipSubtitles
    Skip subtitle splitting and generation.
.PARAMETER SkipAssemble
    Skip FFmpeg dual-version video assembly.
.EXAMPLE
    .\scripts\build_lesson.ps1 -Lesson t1-01-why-aerodynamics
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Lesson,
    [switch]$SkipCapture,
    [switch]$SkipSubtitles,
    [switch]$SkipAssemble
)

$ErrorActionPreference = "Stop"
$WorkspaceRoot = (Split-Path -Parent $PSScriptRoot)
$ContentRoot = "D:\CourseContent"
$BuildDir = Join-Path $ContentRoot "build\$Lesson"
$DeliverDir = Join-Path $ContentRoot "deliver\$Lesson"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "COURSE LESSON BUILD PIPELINE (DUAL-ROOT ARCHITECTURE)" -ForegroundColor Cyan
Write-Host "  Lesson Slug  : $Lesson"
Write-Host "  Workspace    : $WorkspaceRoot (Pure Code & Pipelines)"
Write-Host "  Content Root : $ContentRoot (All Assets & Outputs)"
Write-Host "  Build Dir    : $BuildDir"
Write-Host "  Deliver Dir  : $DeliverDir"
Write-Host "============================================================" -ForegroundColor Cyan

if (-not (Test-Path $BuildDir)) {
    Write-Error "Build directory does not exist: $BuildDir"
    exit 1
}

# 1. Slide Snapshotting (Playwright)
if (-not $SkipCapture) {
    Write-Host "`n[Step 1/3] Capturing 1080P slide snapshots via Playwright..." -ForegroundColor Yellow
    $captureScript = Join-Path $PSScriptRoot "capture_all_shots.mjs"
    if (Test-Path $captureScript) {
        & node $captureScript $Lesson
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to capture slide snapshots!"
            exit $LASTEXITCODE
        }
        Write-Host "  ✓ Slide snapshots captured to: $BuildDir\shots" -ForegroundColor Green
    } else {
        Write-Warning "Capture script not found: $captureScript"
    }
} else {
    Write-Host "`n[Step 1/3] Skipping Slide Snapshotting (-SkipCapture)." -ForegroundColor Gray
}

# 2. Subtitle Generation
if (-not $SkipSubtitles) {
    Write-Host "`n[Step 2/3] Generating synchronized short-form subtitles..." -ForegroundColor Yellow
    $subScript = Join-Path $PSScriptRoot "build_refined_subtitles.py"
    if (Test-Path $subScript) {
        & python $subScript $Lesson
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to generate subtitles!"
            exit $LASTEXITCODE
        }
        Write-Host "  ✓ Subtitles exported to: $DeliverDir" -ForegroundColor Green
    } else {
        Write-Warning "Subtitle script not found: $subScript"
    }
} else {
    Write-Host "`n[Step 2/3] Skipping Subtitle Generation (-SkipSubtitles)." -ForegroundColor Gray
}

# 3. Dual-Version Video Assembly (FFmpeg)
if (-not $SkipAssemble) {
    Write-Host "`n[Step 3/3] Assembling dual-version 1080P videos (Clean & Hardsubbed)..." -ForegroundColor Yellow
    $assembleScript = Join-Path $PSScriptRoot "assemble_t1_01_video.py"
    if (Test-Path $assembleScript) {
        & python $assembleScript $Lesson
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to assemble videos!"
            exit $LASTEXITCODE
        }
        Write-Host "  ✓ Dual-version videos delivered to: $DeliverDir" -ForegroundColor Green
    } else {
        Write-Warning "Assemble script not found: $assembleScript"
    }
} else {
    Write-Host "`n[Step 3/3] Skipping Video Assembly (-SkipAssemble)." -ForegroundColor Gray
}

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "LESSON PRODUCTION COMPLETE: $Lesson" -ForegroundColor Green
Write-Host "  All deliverables verified in: $DeliverDir"
Write-Host "============================================================" -ForegroundColor Cyan

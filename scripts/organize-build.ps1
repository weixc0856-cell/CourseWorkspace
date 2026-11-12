[CmdletBinding()]
param(
    [string]$Workspace = (Split-Path -Parent $PSScriptRoot),
    [switch]$Apply,
    [switch]$EngineCaches
)

# Two buckets:
#   build/<slug>/      temporary and intermediate; safe to delete/rebuild
#   deliver/<slug>/    final, self-contained delivery package; do not delete
#
# This script only moves existing directories. It never deletes a delivery.
# Without -Apply it prints the planned moves.

$root = (Resolve-Path $Workspace).Path
. (Join-Path $PSScriptRoot "_layout.ps1")
$content = Get-ContentRoot -Workspace $root
$moves = New-Object System.Collections.Generic.List[object]

$buildRoot = Join-Path $content "build"
if (Test-Path $buildRoot) {
    Get-ChildItem $buildRoot -Directory | Where-Object { $_.Name -notlike "_*" } | ForEach-Object {
        $slug = $_.Name
        $package = Join-Path $_.FullName "package"
        if (Test-Path $package) {
            $moves.Add([pscustomobject]@{
                Kind   = "package"
                Source = $package
                Target = (Join-Path (Join-Path $content "deliver") $slug)
            })
        }
        $legacy = Join-Path $_.FullName "delivery"
        if (Test-Path $legacy) {
            $moves.Add([pscustomobject]@{
                Kind   = "producer"
                Source = $legacy
                Target = (Join-Path $_.FullName "producer")
            })
        }
    }
}

if ($EngineCaches) {
    $cacheRoot = Join-Path $buildRoot "_engine-cache"
    $engine = @(
        @{ Source = (Join-Path $root "RemotionStudio/public/staging"); Target = (Join-Path $cacheRoot "remotion-staging") },
        @{ Source = (Join-Path $root "ManimSandbox/media");          Target = (Join-Path $cacheRoot "manim-media") },
        @{ Source = (Join-Path $root "MotionStudio/output");         Target = (Join-Path $cacheRoot "motion-output") }
    )
    foreach ($item in $engine) {
        if (Test-Path $item.Source) {
            $moves.Add([pscustomobject]@{ Kind = "engine"; Source = $item.Source; Target = $item.Target })
        }
    }
    $shots = Join-Path $root "CodeVideoStudio/shots"
    if (Test-Path $shots) {
        Get-ChildItem $shots -Directory | ForEach-Object {
            $out = Join-Path $_.FullName "out"
            if (Test-Path $out) {
                $moves.Add([pscustomobject]@{
                    Kind   = "engine"
                    Source = $out
                    Target = (Join-Path (Join-Path $cacheRoot "code-video") $_.Name)
                })
            }
        }
    }
}

if ($moves.Count -eq 0) {
    Write-Host "nothing to organize"
    exit 0
}

$moved = 0
$skipped = 0
foreach ($move in $moves) {
    if (Test-Path $move.Target) {
        Write-Host ("SKIP    {0} -> {1} (target exists)" -f $move.Source, $move.Target)
        $skipped++
        continue
    }
    if (-not $Apply) {
        Write-Host ("PLAN    {0} -> {1}" -f $move.Source, $move.Target)
        continue
    }
    $parent = Split-Path -Parent $move.Target
    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Move-Item -LiteralPath $move.Source -Destination $move.Target
    Write-Host ("MOVED   {0} -> {1}" -f $move.Source, $move.Target)
    $moved++
}

Write-Host ""
Write-Host ("planned={0} moved={1} skipped={2}" -f $moves.Count, $moved, $skipped)
if (-not $Apply) {
    Write-Host "dry run; re-run with -Apply to move. Add -EngineCaches to include engine caches."
}

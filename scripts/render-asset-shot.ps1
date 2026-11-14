[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Spec,
    [ValidateSet("blockout", "preview", "hero")][string]$Profile = "preview",
    [string]$Out,
    [int]$Frames = 0
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $root "config/tools.yaml"
if (-not (Test-Path -LiteralPath $configPath)) {
    throw "config/tools.yaml not found; run scripts/setup.ps1 or copy config/tools.example.yaml"
}
$exe = (Get-Content -LiteralPath $configPath -Encoding UTF8 |
    Select-String -Pattern '^\s*executable:\s*(.+?)\s*$' |
    Select-Object -First 1).Matches.Groups[1].Value.Trim('"', "'")
if ([string]::IsNullOrWhiteSpace($exe) -or -not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "Blender executable not found: $exe"
}
if (-not (Test-Path -LiteralPath $Spec -PathType Leaf)) {
    throw "spec not found: $Spec"
}

# Validate the contract before Blender opens the file.  This is the
# "Scene Spec -> Validator -> Builder" step; skip it only for legacy recipes.
uv run --project CourseControl course-control asset-scene-validate --spec $Spec
if ($LASTEXITCODE -ne 0) {
    throw "spec validation failed: $Spec"
}

$builder = Join-Path $PSScriptRoot "build_asset_scene.py"
$arguments = @("--background", "--factory-startup", "--python", $builder, "--",
    "--spec", (Resolve-Path -LiteralPath $Spec).Path, "--profile", $Profile)
if ($Out) {
    $arguments += @("--out", $Out)
}
if ($Frames -gt 0) {
    $arguments += @("--frames", $Frames)
}
& $exe @arguments
exit $LASTEXITCODE

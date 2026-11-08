[CmdletBinding()]
param(
    [ValidateSet("Code", "Docs", "Course")]
    [string]$Type = "Code",
    [string]$Commit,
    [string]$Base,
    [string[]]$Files = @(),
    [string[]]$Context = @(),
    [switch]$AllowExternalContent,
    [int]$Timeout = 600,
    [switch]$NoIsolation,
    [switch]$DryRun,
    [string]$OutputRoot,
    [switch]$Json
)

# Thin entry point. See ReviewRunner/README.md and docs/研发审核工具.md.
# This script never changes source files and is not part of check.ps1.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot

Push-Location $root
try {
    $argv = @("run", "--type", $Type.ToLower())
    if ($Commit) { $argv += @("--commit", $Commit) }
    if ($Base) { $argv += @("--base", $Base) }
    foreach ($file in $Files) { $argv += @("--files", $file) }
    foreach ($file in $Context) { $argv += @("--context", $file) }
    if ($AllowExternalContent) { $argv += "--allow-external-content" }
    if ($NoIsolation) { $argv += "--no-isolation" }
    if ($DryRun) { $argv += "--dry-run" }
    if ($Json) { $argv += "--json" }
    if ($OutputRoot) { $argv += @("--output-root", $OutputRoot) }
    $argv += @("--timeout", "$Timeout")

    & uv run --project ReviewRunner review-runner @argv
    $code = $LASTEXITCODE
}
finally {
    Pop-Location
}

exit $code

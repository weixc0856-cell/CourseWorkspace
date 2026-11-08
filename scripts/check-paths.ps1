[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
& python (Join-Path $PSScriptRoot "check_paths.py")
exit $LASTEXITCODE

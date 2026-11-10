[CmdletBinding()]
param([switch]$Strict)

$root = Split-Path -Parent $PSScriptRoot
$args = @("run", "--project", (Join-Path $root "CourseControl"), "python",
          (Join-Path $root "scripts/check_evidence.py"), "--workspace", $root)
if ($Strict) { $args += "--strict" }
Push-Location $root
try {
    & uv @args
    exit $LASTEXITCODE
}
finally { Pop-Location }

# Resolve the directory that holds course content (lessons, build, deliver, runtime).
# Mirrors CourseControl/src/course_control/workspace_layout.py:
#   env COURSEWORKSPACE_CONTENT_ROOT  >  config/local-paths.yaml content_root  >  workspace

function Get-ContentRoot {
    param([string]$Workspace = (Split-Path -Parent $PSScriptRoot))

    if ($env:COURSEWORKSPACE_CONTENT_ROOT) {
        return (Resolve-Path $env:COURSEWORKSPACE_CONTENT_ROOT).Path
    }

    $root = (Resolve-Path $Workspace).Path
    $config = Join-Path $root "config/local-paths.yaml"
    if (Test-Path $config) {
        foreach ($line in Get-Content $config) {
            if ($line -match '^\s*content_root\s*:\s*(.+?)\s*$') {
                $value = $matches[1].Trim().Trim('"').Trim("'")
                if ([System.IO.Path]::IsPathRooted($value)) { return $value }
                return (Join-Path $root $value)
            }
        }
    }
    return $root
}

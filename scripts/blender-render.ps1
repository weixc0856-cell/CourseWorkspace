[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Lesson,
    [string]$Task,
    [switch]$Smoke,
    [int]$TimeoutSeconds = 0,
    [string]$Engine
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "_layout.ps1")
$content = Get-ContentRoot -Workspace $root
$configPath = Join-Path $root "config/tools.yaml"

function Stop-WithError {
    param([string]$Message, [int]$Code)
    Write-Host "ERROR: $Message"
    exit $Code
}

function Read-SimpleYaml {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { throw "Config not found: $Path" }
    $result = @{}
    $stack = New-Object System.Collections.ArrayList
    [void]$stack.Add(@{ Indent = -1; Map = $result })
    foreach ($raw in Get-Content -LiteralPath $Path -Encoding UTF8) {
        if ($raw -match '^\s*(#|$)') { continue }
        $indent = $raw.Length - $raw.TrimStart().Length
        $line = $raw.Trim()
        if ($line -notmatch '^([^:]+):\s*(.*)$') { throw "Invalid YAML line: $line" }
        $key = $Matches[1].Trim()
        $value = $Matches[2].Trim()
        while ($stack.Count -gt 1 -and $indent -le $stack[$stack.Count - 1].Indent) {
            $stack.RemoveAt($stack.Count - 1)
        }
        $parent = $stack[$stack.Count - 1].Map
        if ($value -eq "") {
            $child = @{}
            $parent[$key] = $child
            [void]$stack.Add(@{ Indent = $indent; Map = $child })
        }
        else {
            if ($value -match '^"(.*)"$') { $value = $Matches[1] }
            elseif ($value -match "^'(.*)'$") { $value = $Matches[1] }
            if ($value -match '^(?i:true|false)$') { $value = [bool]::Parse($value.ToLower()) }
            elseif ($value -match '^-?\d+$') { $value = [int]$value }
            $parent[$key] = $value
        }
    }
    return $result
}

function Quote-Arg {
    param([string]$Value)
    if ($Value -match '^[A-Za-z0-9_./:\\-]+$') { return $Value }
    return '"' + ($Value -replace '"', '\"') + '"'
}

if ($Lesson -notmatch '^[a-z0-9]+(?:-[a-z0-9]+)*$') {
    Stop-WithError "invalid lesson slug: $Lesson" 2
}
if ($Smoke -and $Task) {
    Stop-WithError "use either -Smoke or -Task, not both" 2
}
if (-not $Smoke -and -not $Task) {
    Stop-WithError "either -Smoke or -Task is required" 2
}

if (-not (Test-Path -LiteralPath $configPath)) {
    Stop-WithError "config/tools.yaml not found; run scripts/setup.ps1 or copy config/tools.example.yaml" 3
}
$cfg = Read-SimpleYaml $configPath
$exe = [string]$cfg["blender"]["executable"]
if ([string]::IsNullOrWhiteSpace($exe) -or -not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    Stop-WithError "Blender executable not found: $exe" 3
}

$timeout = if ($TimeoutSeconds -gt 0) { $TimeoutSeconds } else { [int]$cfg["blender"]["timeout_seconds"] }
if ($timeout -le 0) { Stop-WithError "invalid timeout_seconds: $timeout" 3 }

$defaultEngine = [string]$cfg["blender"]["engine"]
$taskData = $null

if ($Smoke) {
    $script = Join-Path $root "BlenderStudio/scripts/render_smoke.py"
    $output = Join-Path $content "build/$Lesson/blender/smoke.mp4"
    $logName = "blender-smoke.log"
    $pyArgs = @("--lesson", $Lesson, "--out", $output)
    $engineOverride = if ($Engine) { $Engine } else { $defaultEngine }
}
else {
    $taskPath = if ([IO.Path]::IsPathRooted($Task)) { $Task } else { Join-Path $root $Task }
    if (-not (Test-Path -LiteralPath $taskPath -PathType Leaf)) {
        Stop-WithError "task not found: $taskPath" 4
    }
    $taskData = Get-Content -LiteralPath $taskPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $output = [string]$taskData.output
    if ([string]::IsNullOrWhiteSpace($output) -and $taskData.render) {
        $output = [string]$taskData.render.output
    }
    if ([string]::IsNullOrWhiteSpace($output)) {
        Stop-WithError "task output is missing: $taskPath" 4
    }
    if (-not [IO.Path]::IsPathRooted($output)) {
        # build/ paths belong to the content root, which may sit outside the
        # workspace.  Resolving them against the workspace was the old bug.
        if ($output.StartsWith("build/") -or $output.StartsWith("build\")) {
            $output = Join-Path $content $output
        }
        else { $output = Join-Path $root $output }
    }
    $script = Join-Path $root "BlenderStudio/scripts/render_shot.py"
    $logName = "blender-" + [IO.Path]::GetFileNameWithoutExtension($taskPath) + ".log"
    $pyArgs = @("--task", $taskPath)
    $taskEngine = [string]$taskData.engine
    if ([string]::IsNullOrWhiteSpace($taskEngine) -and $taskData.render) {
        $taskEngine = [string]$taskData.render.engine
    }
    $engineOverride = if ($Engine) { $Engine } elseif ([string]::IsNullOrWhiteSpace($taskEngine)) { $defaultEngine } else { $null }
}

if ($engineOverride) { $pyArgs += @("--engine", $engineOverride) }

$allowedRoot = [IO.Path]::GetFullPath((Join-Path $content "build/$Lesson/blender"))
$outputAbs = [IO.Path]::GetFullPath($output)
$prefix = $allowedRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $outputAbs.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
    Stop-WithError "output must be inside build/$Lesson/blender/: $outputAbs" 5
}

$logDir = Join-Path $content "build/$Lesson/logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outputAbs) | Out-Null

$versionOutput = & $exe --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Stop-WithError "Blender --version failed with exit code $LASTEXITCODE" 6
}

$blenderArgs = @(
    "--background",
    "--factory-startup",
    "--python-exit-code", "1",
    "--python", $script,
    "--"
) + $pyArgs

$argString = ($blenderArgs | ForEach-Object { Quote-Arg $_ }) -join " "
$logPath = Join-Path $logDir $logName

$start = Get-Date
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $exe
$psi.Arguments = $argString
$psi.WorkingDirectory = $root
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true
$psi.EnvironmentVariables["COURSE_CONTENT_ROOT"] = $content
if ($env:COURSE_DESIGN_JSON) { $psi.EnvironmentVariables["COURSE_DESIGN_JSON"] = $env:COURSE_DESIGN_JSON }
try {
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
}
catch { }

$process = New-Object System.Diagnostics.Process
$process.StartInfo = $psi
$null = $process.Start()
$stdoutTask = $process.StandardOutput.ReadToEndAsync()
$stderrTask = $process.StandardError.ReadToEndAsync()

$timedOut = -not $process.WaitForExit($timeout * 1000)
if ($timedOut) {
    try { $process.Kill() } catch { }
    try { $process.WaitForExit() } catch { }
}
$end = Get-Date

$stdoutText = ""
$stderrText = ""
try { if ($stdoutTask.Wait(5000)) { $stdoutText = $stdoutTask.Result } } catch { }
try { if ($stderrTask.Wait(5000)) { $stderrText = $stderrTask.Result } } catch { }

$code = if ($timedOut) { 124 } else { $process.ExitCode }
if ($null -eq $code) {
    Write-Host "ERROR: Blender exit code unavailable"
    $code = 1
}

$logLines = New-Object System.Collections.Generic.List[string]
$logLines.Add("COMMAND: `"$exe`" $argString")
$logLines.Add("BLENDER_VERSION: " + (($versionOutput | Select-Object -First 3) -join " "))
$logLines.Add("START: " + $start.ToString("o"))
$logLines.Add("END: " + $end.ToString("o"))
$logLines.Add("EXIT_CODE: $code")
$logLines.Add("TIMEOUT_SECONDS: $timeout")
if ($timedOut) { $logLines.Add("TIMED_OUT: true") }
$logLines.Add("--- STDOUT ---")
if ($stdoutText.Length -gt 0) { $logLines.AddRange([string[]]($stdoutText -split "`r?`n")) }
$logLines.Add("--- STDERR ---")
if ($stderrText.Length -gt 0) { $logLines.AddRange([string[]]($stderrText -split "`r?`n")) }
Set-Content -LiteralPath $logPath -Value $logLines -Encoding UTF8

if ($code -eq 0 -and -not (Test-Path -LiteralPath $outputAbs -PathType Leaf)) {
    Write-Host "ERROR: Blender exited 0 but output is missing: $outputAbs"
    exit 7
}

# Blender on Windows can return from the parent process before a child writer
# has finalised the MP4 (moov atom).  Wait for the file to stop growing.
if ($code -eq 0 -and (Test-Path -LiteralPath $outputAbs -PathType Leaf)) {
    $lastSize = -1
    $stable = 0
    $grace = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $grace) {
        $size = (Get-Item -LiteralPath $outputAbs).Length
        if ($size -gt 0 -and $size -eq $lastSize) { $stable++ } else { $stable = 0 }
        $lastSize = $size
        if ($stable -ge 3) { break }
        Start-Sleep -Milliseconds 1000
    }
    Write-Host ("BLENDER_OUTPUT_BYTES " + $lastSize)
}

if ($code -eq 0) {
    Write-Host "OK: $outputAbs"
}
exit $code

$ErrorActionPreference = 'Stop'

$projectDirectory = $PSScriptRoot
$pythonExecutable = Join-Path $projectDirectory '.venv\Scripts\python.exe'
$sourceVenvPython = 'C:\Workspace\vsti-webui\.venv\Scripts\python.exe'
$bindAddress = if ($env:YAMAHA_BIND_HOST) { $env:YAMAHA_BIND_HOST } else { '0.0.0.0' }
$webPort = if ($env:YAMAHA_PORT) { [int]$env:YAMAHA_PORT } else { 8789 }
$pcmPort = if ($env:VSTI_PCM_PORT) { [int]$env:VSTI_PCM_PORT } else { 9998 }

function Stop-ProcessIdIfSafe {
    param([int]$TargetProcessId)
    if ($TargetProcessId -le 0 -or $TargetProcessId -eq $PID) { return }
    try {
        $target = Get-Process -Id $TargetProcessId -ErrorAction Stop
        Stop-Process -Id $TargetProcessId -Force -ErrorAction Stop
        Write-Output ('Stopped stale process pid={0} name={1}' -f $TargetProcessId, $target.ProcessName)
    } catch {
        Write-Output ('Skip stale process pid={0}: {1}' -f $TargetProcessId, $_.Exception.Message)
    }
}

$portOwners = New-Object System.Collections.Generic.HashSet[int]
Get-NetTCPConnection -LocalPort $webPort -ErrorAction SilentlyContinue |
    Where-Object { $_.State -eq 'Listen' } |
    ForEach-Object { [void]$portOwners.Add([int]$_.OwningProcess) }
Get-NetUDPEndpoint -LocalPort $pcmPort -ErrorAction SilentlyContinue |
    ForEach-Object { [void]$portOwners.Add([int]$_.OwningProcess) }
foreach ($ownerProcessId in $portOwners) {
    Stop-ProcessIdIfSafe -TargetProcessId $ownerProcessId
}

$escapedProjectDirectory = [regex]::Escape($projectDirectory)
Get-CimInstance Win32_Process |
    Where-Object {
        $_.ProcessId -ne $PID -and
        $_.CommandLine -and
        (
            ($_.Name -in @('python.exe', 'ffmpeg.exe') -and $_.CommandLine -match $escapedProjectDirectory) -or
            ($_.Name -eq 'ffmpeg.exe' -and $_.CommandLine -match 'data\\hls\\stream\.m3u8')
        )
    } |
    ForEach-Object { Stop-ProcessIdIfSafe -TargetProcessId ([int]$_.ProcessId) }

Start-Sleep -Milliseconds 500

if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    if (Test-Path -LiteralPath $sourceVenvPython) {
        $pythonExecutable = $sourceVenvPython
    } else {
        throw 'Python environment not found. Run Setup-VstiWebUi.ps1 first.'
    }
}

Set-Location -LiteralPath $projectDirectory
& $pythonExecutable -m uvicorn app.main:app --host $bindAddress --port $webPort

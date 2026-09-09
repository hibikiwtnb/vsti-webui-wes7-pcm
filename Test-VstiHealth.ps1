param(
    [switch]$PlayTest,
    [string]$FileId,
    [int]$ObserveSeconds = 5
)

$ErrorActionPreference = 'Continue'

$vmName = 'WES7-VSTi-Appliance'
$guestHost = if ($env:VSTI_GUEST_HOST) { $env:VSTI_GUEST_HOST } else { '172.19.32.190' }
$sshPort = 22
$webHost = if ($env:YAMAHA_BIND_CHECK_HOST) { $env:YAMAHA_BIND_CHECK_HOST } else { '127.0.0.1' }
$webPort = if ($env:YAMAHA_PORT) { [int]$env:YAMAHA_PORT } else { 8789 }
$pcmPort = if ($env:VSTI_PCM_PORT) { [int]$env:VSTI_PCM_PORT } else { 9998 }
$projectDirectory = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$hlsDirectory = Join-Path $projectDirectory 'data\hls'
$failures = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

function Write-Check {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][string]$Status,
        [string]$Detail = ''
    )
    Write-Output ('{0,-24} {1,-6} {2}' -f $Name, $Status, $Detail)
}

function Add-Failure { param([string]$Message) [void]$failures.Add($Message) }
function Add-Warning { param([string]$Message) [void]$warnings.Add($Message) }

function Get-State {
    param([string]$BaseUrl)
    Invoke-RestMethod -Uri ($BaseUrl + '/api/state') -TimeoutSec 3
}

Write-Output 'VSTi WebUI / WES7 health check'
Write-Output ('Timestamp: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
Write-Output ''

$vm = $null
try { $vm = Get-VM -Name $vmName -ErrorAction Stop } catch {}
if ($vm) {
    $vmDetail = 'state={0} uptime={1}' -f $vm.State, $vm.Uptime
    if ($vm.State -eq 'Running') { Write-Check 'Hyper-V VM' 'OK' $vmDetail } else { Write-Check 'Hyper-V VM' 'FAIL' $vmDetail; Add-Failure 'WES7 VM is not running.' }
} else {
    Write-Check 'Hyper-V VM' 'WARN' ('not found: ' + $vmName)
    Add-Warning 'Hyper-V VM was not found from this shell.'
}

$vhdPath = 'C:\Workspace\wes7-vsti-appliance\vm\wes7-appliance.vhd'
if (Test-Path -LiteralPath $vhdPath) {
    $diskImage = Get-DiskImage -ImagePath $vhdPath -ErrorAction SilentlyContinue
    if ($diskImage -and $diskImage.Attached) {
        Write-Check 'VHD mounted on host' 'FAIL' 'attached=true'
        Add-Failure 'WES7 VHD is mounted on host; VM cannot safely own the disk.'
    } else {
        Write-Check 'VHD mounted on host' 'OK' 'attached=false'
    }
}

$sshTest = Test-NetConnection -ComputerName $guestHost -Port $sshPort -InformationLevel Quiet -WarningAction SilentlyContinue
if ($sshTest) { Write-Check 'Guest SSH IPv4' 'OK' ("$guestHost`:$sshPort") } else { Write-Check 'Guest SSH IPv4' 'FAIL' ("$guestHost`:$sshPort"); Add-Failure 'WES7 SSH is not reachable over IPv4.' }

$webUrl = "http://$webHost`:$webPort"
$webTest = Test-NetConnection -ComputerName $webHost -Port $webPort -InformationLevel Quiet -WarningAction SilentlyContinue
if ($webTest) { Write-Check 'WebUI TCP' 'OK' $webUrl } else { Write-Check 'WebUI TCP' 'FAIL' $webUrl; Add-Failure 'WebUI TCP port is not reachable.' }

$listenerOwners = @(Get-NetTCPConnection -LocalPort $webPort -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $_.OwningProcess } | Sort-Object -Unique)
if ($listenerOwners.Count -eq 1) {
    Write-Check 'WebUI listener owner' 'OK' ('pid=' + $listenerOwners[0])
} elseif ($listenerOwners.Count -eq 0) {
    Write-Check 'WebUI listener owner' 'FAIL' 'none'
    Add-Failure 'No process owns the WebUI listen port.'
} else {
    Write-Check 'WebUI listener owner' 'FAIL' ('pids=' + ($listenerOwners -join ','))
    Add-Failure 'Multiple processes own the WebUI listen port.'
}

$uvicornProcesses = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'uvicorn app\.main:app' -and $_.CommandLine -match [regex]::Escape($webPort.ToString()) })
$uvicornIds = ($uvicornProcesses | ForEach-Object { $_.ProcessId }) -join ','
if ($uvicornProcesses.Count -ge 1) {
    Write-Check 'Uvicorn process tree' 'OK' ('count={0} pids={1}' -f $uvicornProcesses.Count, $uvicornIds)
} else {
    Write-Check 'Uvicorn process tree' 'FAIL' 'count=0'
    Add-Failure 'No uvicorn process was found.'
}

$pcmEndpoints = @(Get-NetUDPEndpoint -LocalPort $pcmPort -ErrorAction SilentlyContinue)
if ($pcmEndpoints.Count -gt 0) {
    $owners = ($pcmEndpoints | ForEach-Object { $_.OwningProcess } | Sort-Object -Unique) -join ','
    Write-Check 'PCM UDP listener' 'OK' ("0.0.0.0`:$pcmPort owners=$owners")
} else {
    Write-Check 'PCM UDP listener' 'FAIL' ("port=$pcmPort")
    Add-Failure 'Host PCM UDP listener is missing.'
}

try {
    $health = Invoke-RestMethod -Uri ($webUrl + '/health') -TimeoutSec 3
    Write-Check 'HTTP /health' 'OK' ('status=' + $health.status)
} catch {
    Write-Check 'HTTP /health' 'FAIL' $_.Exception.Message
    Add-Failure 'WebUI /health failed.'
}

$state = $null
try {
    $state = Get-State -BaseUrl $webUrl
    $packetText = 'packets={0} nonSilent={1} age={2}s ready={3}' -f $state.stream.packets, $state.stream.non_silent_packets, $state.stream.last_packet_age_seconds, $state.stream.ready
    if ($state.stream.running -and $state.stream.ready -and [double]$state.stream.last_packet_age_seconds -lt 3) {
        Write-Check 'PCM stream state' 'OK' $packetText
    } else {
        Write-Check 'PCM stream state' 'FAIL' $packetText
        Add-Failure 'PCM stream is not fresh or not ready.'
    }
    if ($state.playback.port_available) {
        Write-Check 'MIDI target' 'OK' $state.playback.port_name
    } else {
        Write-Check 'MIDI target' 'FAIL' $state.playback.port_name
        Add-Failure 'MIDI target is not available.'
    }
} catch {
    Write-Check 'HTTP /api/state' 'FAIL' $_.Exception.Message
    Add-Failure 'WebUI /api/state failed.'
}

if (Test-Path -LiteralPath $hlsDirectory) {
    $playlist = Join-Path $hlsDirectory 'stream.m3u8'
    if (Test-Path -LiteralPath $playlist) {
        $playlistItem = Get-Item -LiteralPath $playlist
        $ageSeconds = [math]::Round(((Get-Date) - $playlistItem.LastWriteTime).TotalSeconds, 1)
        if ($ageSeconds -le 3 -and $playlistItem.Length -gt 0) {
            Write-Check 'HLS playlist' 'OK' ('age={0}s size={1}B' -f $ageSeconds, $playlistItem.Length)
        } else {
            Write-Check 'HLS playlist' 'FAIL' ('age={0}s size={1}B' -f $ageSeconds, $playlistItem.Length)
            Add-Failure 'HLS playlist is stale or empty.'
        }
    } else {
        Write-Check 'HLS playlist' 'FAIL' 'missing stream.m3u8'
        Add-Failure 'HLS playlist is missing.'
    }
    $segments = @(Get-ChildItem -LiteralPath $hlsDirectory -Filter 'segment-*.m4s' -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 3)
    if ($segments.Count -gt 0) {
        $segmentInfo = ($segments | ForEach-Object { '{0}:{1}B' -f $_.Name, $_.Length }) -join ' '
        Write-Check 'HLS segments' 'OK' $segmentInfo
    } else {
        Write-Check 'HLS segments' 'FAIL' 'none'
        Add-Failure 'No HLS media segments found.'
    }
} else {
    Write-Check 'HLS directory' 'FAIL' $hlsDirectory
    Add-Failure 'HLS directory is missing.'
}

if ($PlayTest) {
    Write-Output ''
    Write-Output 'Play test'
    if (-not $FileId) {
        try {
            $midiList = Invoke-RestMethod -Uri ($webUrl + '/api/midi') -TimeoutSec 3
            if ($midiList.items.Count -gt 0) { $FileId = $midiList.items[0].id }
        } catch {}
    }
    if (-not $FileId) {
        Write-Check 'Play test file' 'FAIL' 'no MIDI file available'
        Add-Failure 'PlayTest requested but no MIDI file is available.'
    } else {
        $before = $null
        try { $before = Get-State -BaseUrl $webUrl } catch {}
        try {
            $body = @{ file_id = $FileId; synth = 'yamaha-syxg2006le'; start_seconds = 0 } | ConvertTo-Json -Compress
            Invoke-RestMethod -Uri ($webUrl + '/api/synth/play') -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 5 | Out-Null
            Start-Sleep -Seconds $ObserveSeconds
            $after = Get-State -BaseUrl $webUrl
            $beforeNonSilent = if ($before) { [int64]$before.stream.non_silent_packets } else { 0 }
            $afterNonSilent = [int64]$after.stream.non_silent_packets
            $delta = $afterNonSilent - $beforeNonSilent
            if ($delta -gt 0) {
                Write-Check 'Play non-silent PCM' 'OK' ('file={0} delta={1}' -f $FileId, $delta)
            } else {
                Write-Check 'Play non-silent PCM' 'FAIL' ('file={0} delta={1}' -f $FileId, $delta)
                Add-Failure 'PlayTest did not produce non-silent PCM.'
            }
        } catch {
            Write-Check 'Play request' 'FAIL' $_.Exception.Message
            Add-Failure 'PlayTest request failed.'
        }
    }
}

Write-Output ''
if ($failures.Count -eq 0) {
    if ($warnings.Count -eq 0) {
        Write-Output 'OVERALL OK'
        exit 0
    }
    Write-Output 'OVERALL WARN'
    foreach ($warning in $warnings) { Write-Output ('WARN: ' + $warning) }
    exit 1
}
Write-Output 'OVERALL FAIL'
foreach ($failure in $failures) { Write-Output ('FAIL: ' + $failure) }
foreach ($warning in $warnings) { Write-Output ('WARN: ' + $warning) }
exit 2

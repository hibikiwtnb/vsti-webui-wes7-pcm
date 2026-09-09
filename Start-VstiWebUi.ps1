$ErrorActionPreference = 'Stop'

$projectDirectory = $PSScriptRoot
$pythonExecutable = Join-Path $projectDirectory '.venv\Scripts\python.exe'
$sourceVenvPython = 'C:\Workspace\vsti-webui\.venv\Scripts\python.exe'
$bindAddress = if ($env:YAMAHA_BIND_HOST) { $env:YAMAHA_BIND_HOST } else { '0.0.0.0' }
$webPort = if ($env:YAMAHA_PORT) { [int]$env:YAMAHA_PORT } else { 8789 }

if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    if (Test-Path -LiteralPath $sourceVenvPython) {
        $pythonExecutable = $sourceVenvPython
    } else {
        throw "Python environment not found. Run Setup-VstiWebUi.ps1 first."
    }
}

Set-Location -LiteralPath $projectDirectory
& $pythonExecutable -m uvicorn app.main:app --host $bindAddress --port $webPort

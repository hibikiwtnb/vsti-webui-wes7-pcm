$ErrorActionPreference = 'Stop'

$projectDirectory = $PSScriptRoot
$virtualEnvironment = Join-Path $projectDirectory '.venv'
$pythonExecutable = Join-Path $virtualEnvironment 'Scripts\python.exe'

if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    $pythonLauncher = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if ($pythonLauncher) {
        & $pythonLauncher.Source -3.11 -m venv $virtualEnvironment
    } else {
        $systemPython = Get-Command 'python.exe' -ErrorAction Stop
        & $systemPython.Source -m venv $virtualEnvironment
    }
}

& $pythonExecutable -m pip install --upgrade pip
& $pythonExecutable -m pip install -r (Join-Path $projectDirectory 'requirements.txt')

Write-Host 'VSTi WebUI setup completed.'
Write-Host 'Run Start-VstiWebUi.ps1 to start the WebUI.'

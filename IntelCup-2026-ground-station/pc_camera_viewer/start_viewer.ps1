$ErrorActionPreference = "Stop"

$viewerDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $viewerDir ".venv\Scripts\python.exe"
$viewerScript = Join-Path $viewerDir "example_preview.py"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "Camera viewer environment is missing.",
        "AMB82 Camera",
        "OK",
        "Error"
    ) | Out-Null
    exit 1
}

Set-Location -LiteralPath $viewerDir
& $pythonExe $viewerScript


param(
    [Parameter(Mandatory=$true)][string]$CoreDir,
    [string]$Python,
    [ValidateSet('esp32dev','wokwi')][string[]]$Environment=@('esp32dev','wokwi')
)
$ErrorActionPreference='Stop'
$project=Split-Path $PSScriptRoot -Parent
if (!$Python) { $Python=Join-Path $project '.tools/venv/Scripts/python.exe' }
$Python=(Resolve-Path -LiteralPath $Python).Path
# Resolve before changing directory. Use a dedicated, short absolute path on Windows.
$CoreDir=[IO.Path]::GetFullPath($CoreDir)
$previousTemp=$env:TEMP
$previousTmp=$env:TMP
$previousCore=$env:PLATFORMIO_CORE_DIR
New-Item -ItemType Directory -Force (Join-Path $project 'test-results') | Out-Null
New-Item -ItemType Directory -Force (Join-Path $CoreDir 'tmp') | Out-Null
Push-Location $project
try {
    $env:PLATFORMIO_CORE_DIR=$CoreDir
    $env:TEMP=Join-Path $CoreDir 'tmp'
    $env:TMP=$env:TEMP
    foreach ($target in $Environment) {
        # Compilation only. No upload, serial, or device enumeration.
        & $Python -m platformio run -e $target -j 2 2>&1 |
            Tee-Object (Join-Path $project "test-results/build-$target.log")
        if ($LASTEXITCODE -ne 0) { throw "ESP32 compilation failed: $target" }
    }
} finally {
    $env:PLATFORMIO_CORE_DIR=$previousCore
    $env:TEMP=$previousTemp
    $env:TMP=$previousTmp
    Pop-Location
}

$ErrorActionPreference='Stop'
$project=Split-Path $PSScriptRoot -Parent
$previousCore=$env:PLATFORMIO_CORE_DIR
Push-Location $project
try {
    $env:PLATFORMIO_CORE_DIR=Join-Path $project '.tools/pio'
    & '.tools/venv/Scripts/python.exe' -m platformio run -e esp32dev
    if ($LASTEXITCODE -ne 0) { throw 'ESP32 compilation failed' }
} finally {
    $env:PLATFORMIO_CORE_DIR=$previousCore
    Pop-Location
}

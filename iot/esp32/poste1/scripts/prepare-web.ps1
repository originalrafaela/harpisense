param([string]$OutputDir)
$ErrorActionPreference='Stop'
$project=Split-Path $PSScriptRoot -Parent
if (!$OutputDir) { $OutputDir=Join-Path $project '.tools/wokwi-web' }
$OutputDir=[IO.Path]::GetFullPath($OutputDir)
$binary=Join-Path $project '.pio/build/wokwi/firmware.bin'
$manifest=Get-Content (Join-Path $project 'evidence/build-20261101/artifacts.json') -Raw | ConvertFrom-Json
$approved=$manifest | Where-Object { $_.environment -eq 'wokwi' -and $_.file -eq 'firmware.bin' }
if (!$approved -or (Get-FileHash -LiteralPath $binary).Hash -ne $approved.sha256) {
    throw 'Expected approved Wokwi binary missing or changed. Review build evidence before exporting.'
}
New-Item -ItemType Directory -Force $OutputDir | Out-Null
Copy-Item -LiteralPath $binary -Destination (Join-Path $OutputDir 'firmware.bin')
Copy-Item -LiteralPath (Join-Path $project 'diagram.json') -Destination (Join-Path $OutputDir 'diagram.json')
$files=foreach ($name in @('firmware.bin','diagram.json')) {
    [ordered]@{file=$name;sha256=(Get-FileHash -LiteralPath (Join-Path $OutputDir $name)).Hash}
}
$files | ConvertTo-Json | Set-Content (Join-Path $OutputDir 'SHA256.json')
@'
Poste 1: simulation only, never flash firmware.bin to a physical board.
Open https://wokwi.com/projects/new/esp32 in your browser.
Replace the entire diagram.json editor content with this diagram.json.
Click in the code editor, press F1, select Upload Firmware and Start Simulation.
Select this firmware.bin. Do not press the normal Compile/Run button for sketch.ino.
No CLI token is required for this anonymous web path. Saving the project may require sign-in.
Use the LDR slider: 100000 -> 100 -> 0.1 -> 100 -> 100000 lux.
Wait for fresh serial samples in each phase; middle values should preserve the LED state.
MQTT is closed. GPIO34 LDR, GPIO25 LED. No physical calibration or USB upload.
Full instructions and current results are in simulation/EXECUTAR.md in the repository.
'@ | Set-Content (Join-Path $OutputDir 'LEIA-ME.txt')
$archive=Join-Path (Split-Path $OutputDir -Parent) 'wokwi-web.zip'
$archiveFiles=@('firmware.bin','diagram.json','SHA256.json','LEIA-ME.txt') | ForEach-Object { Join-Path $OutputDir $_ }
Compress-Archive -LiteralPath $archiveFiles -DestinationPath $archive -Force
Write-Output "Web files: $OutputDir"
Write-Output "Archive: $archive"
Write-Output 'No compilation, device access, or flash operation performed.'

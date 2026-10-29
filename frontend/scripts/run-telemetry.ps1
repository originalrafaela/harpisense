# Serve the tested integration against the existing P11, with no VM writes.
$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
$previousScope = $env:VITE_P11_RESOURCES
try {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backup = Join-Path 'local-evidence/deployment-backups' $stamp
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    git rev-parse HEAD | Set-Content (Join-Path $backup 'source-head.txt')
    if (Test-Path -LiteralPath 'dist') {
        Copy-Item -LiteralPath 'dist' -Destination (Join-Path $backup 'dist') -Recurse
    }
    $env:VITE_P11_RESOURCES = 'telemetry'
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Build failed; previous artifact is preserved in the backup.' }
    Write-Host "Artifact backup: $backup"
    Write-Host 'P11 tunnel required at 127.0.0.1:18000. No VM service is restarted.'
    npm.cmd run preview
    if ($LASTEXITCODE -ne 0) { throw 'Preview server stopped with an error.' }
} finally {
    $env:VITE_P11_RESOURCES = $previousScope
    Pop-Location
}

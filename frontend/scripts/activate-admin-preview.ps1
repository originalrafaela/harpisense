param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$frontendRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$candidateRoot = Join-Path $frontendRoot 'local-evidence/auth-candidate-dist'
$manifestPath = Join-Path $frontendRoot 'local-evidence/auth-candidate-manifest.json'
$candidate = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
foreach ($entry in $candidate.files.PSObject.Properties) {
    $filePath = [IO.Path]::GetFullPath((Join-Path $candidateRoot $entry.Name))
    if (-not $filePath.StartsWith($candidateRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Caminho fora do artefato candidato.'
    }
    if ((Get-FileHash -LiteralPath $filePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) {
        throw "Artefato alterado: $($entry.Name)"
    }
}
# Read-only handshake: the old P11 Basic bootstrap must never pass this gate.
foreach ($apiPath in '/api/v1/admin-auth/session','/api/v1/p11/health') {
    $response = Invoke-WebRequest -Uri ('http://127.0.0.1:18000' + $apiPath) -SkipHttpErrorCheck -TimeoutSec 10
    if ([int]$response.StatusCode -ne 401 -or ($response.Headers['WWW-Authenticate'] -join '') -ne 'Bearer') {
        throw 'API ainda não confirmou autenticação por sessão. Não publicar o frontend candidato.'
    }
}
if ($CheckOnly) { Write-Host 'Artefato íntegro; API exige sessão Bearer.'; return }
$listeners = @(Get-NetTCPConnection -LocalPort 4174 -State Listen -ErrorAction SilentlyContinue)
$previewProcess = $null
if ($listeners.Count -gt 0) {
    $processIds = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($processIds.Count -ne 1) { throw 'Mais de um processo na porta de publicação; inspecionar antes de reiniciar.' }
    $previewProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($processIds[0])"
    if ($previewProcess.Name -ne 'node.exe' -or $previewProcess.CommandLine -notlike "*$frontendRoot*" -or $previewProcess.CommandLine -notmatch '\bpreview\b') {
        throw 'Porta 4174 pertence a outro processo. Nenhum processo foi encerrado.'
    }
}
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss-ff'
$backupRoot = Join-Path $frontendRoot "local-evidence/deployment-backups/auth-$stamp"
New-Item -ItemType Directory -Path $backupRoot | Out-Null
$distRoot = Join-Path $frontendRoot 'dist'
if (Test-Path -LiteralPath $distRoot) { Copy-Item -LiteralPath $distRoot -Destination (Join-Path $backupRoot 'dist') -Recurse }
$candidate | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $backupRoot 'candidate.json') -Encoding utf8
# Copy assets before switching the entrypoint; no deletion of prior evidence/artifacts.
if (!(Test-Path -LiteralPath $distRoot)) { New-Item -ItemType Directory -Path $distRoot | Out-Null }
Get-ChildItem -LiteralPath $candidateRoot | Where-Object Name -ne 'index.html' | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $distRoot -Recurse -Force
}
Copy-Item -LiteralPath (Join-Path $candidateRoot 'index.html') -Destination (Join-Path $distRoot 'index.html') -Force
if ($previewProcess) { Stop-Process -Id $previewProcess.ProcessId }
$nodeCommand = (Get-Command node.exe).Source
$vitePath = Join-Path $frontendRoot 'node_modules/vite/bin/vite.js'
$arguments = @(('"' + $vitePath + '"'),'preview','--host','127.0.0.1','--port','4174')
$server = Start-Process -FilePath $nodeCommand -ArgumentList $arguments -WorkingDirectory $frontendRoot -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $backupRoot 'preview.stdout.log') -RedirectStandardError (Join-Path $backupRoot 'preview.stderr.log')
[ordered]@{source_commit=$candidate.source_commit;release=$candidate.release;process_id=$server.Id;backup=$backupRoot;started_at=[DateTime]::UtcNow.ToString('o')} |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $frontendRoot 'local-evidence/auth-preview-deployment.json') -Encoding utf8
Write-Host "Frontend publicado. Processo: $($server.Id). Backup: $backupRoot"

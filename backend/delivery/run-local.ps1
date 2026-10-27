param([string]$Python = 'python', [int]$Port = 18010)
$ErrorActionPreference = 'Stop'
foreach ($name in @('DATABASE_URL','HARPISENSE_ADMIN_USER','HARPISENSE_ADMIN_PASSWORD')) {
  if (-not [Environment]::GetEnvironmentVariable($name)) { throw "Defina $name no ambiente. Nenhuma credencial padrão é criada." }
}
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$env:PYTHONPATH = @((Join-Path $repoRoot 'backend'),(Join-Path $repoRoot 'backend/domain'),(Join-Path $repoRoot 'genai'),$env:PYTHONPATH) -join [IO.Path]::PathSeparator
& $Python -m uvicorn delivery.app:build_app --factory --host 127.0.0.1 --port $Port --no-access-log
exit $LASTEXITCODE

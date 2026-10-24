param([string]$PythonPath, [switch]$DownloadModel)
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '../..')
$root = Join-Path (Get-Location) '.local-harpia'
New-Item -ItemType Directory -Force $root,(Join-Path $root 'models'),(Join-Path $root 'results') | Out-Null
$lock = Get-Content -Raw genai/artifacts.lock.json | ConvertFrom-Json
function Check-Exit([string]$Step) { if ($LASTEXITCODE -ne 0) { throw "Falhou: $Step (exit $LASTEXITCODE)" } }
if (!$PythonPath) {
    $env:UV_CACHE_DIR = Join-Path $root 'uv-cache'
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $root 'python'
    & uv python install $lock.python
    Check-Exit 'Python dedicado'
    $PythonPath = Join-Path $env:UV_PYTHON_INSTALL_DIR "cpython-$($lock.python)-windows-x86_64-none/python.exe"
}
if (!(Test-Path (Join-Path $root 'venv/Scripts/python.exe'))) {
    & $PythonPath -m venv (Join-Path $root 'venv')
    Check-Exit 'venv dedicada'
}
$runtime = Join-Path $root 'runtime/BitNet'
if (!(Test-Path (Join-Path $runtime '.git'))) {
    & git -c core.longpaths=true clone --no-checkout $lock.runtime.url $runtime
    Check-Exit 'clone runtime'
    & git -C $runtime -c core.longpaths=true checkout --detach $lock.runtime.revision
    Check-Exit 'revisão runtime'
}
$revision = & git -C $runtime rev-parse HEAD
Check-Exit 'ler revisão'
if ($revision -ne $lock.runtime.revision) { throw 'Runtime existente difere do lock. Não foi alterado.' }
& git -C $runtime -c core.longpaths=true submodule update --init --recursive
Check-Exit 'submódulos oficiais'
if ($DownloadModel) {
    $destination = Join-Path $root "models/$($lock.model.filename)"
    if (!(Test-Path $destination)) {
        $free = (Get-PSDrive -Name (Split-Path -Qualifier $root).TrimEnd(':')).Free
        if ($free -lt ($lock.model.bytes + 2GB)) { throw 'Espaço insuficiente (pesos + margem 2 GiB)' }
        $partial = "$destination.partial"
        $url = "$($lock.model.repository)/resolve/$($lock.model.revision)/$($lock.model.filename)"
        & curl.exe --fail --location --retry 2 --continue-at - --output $partial $url
        Check-Exit 'download pesos'
        if ((Get-FileHash -Algorithm SHA256 -LiteralPath $partial).Hash.ToLowerInvariant() -ne $lock.model.sha256) {
            throw 'SHA-256 divergente; arquivo parcial preservado para diagnóstico'
        }
        Move-Item -LiteralPath $partial -Destination $destination
    }
    if ((Get-Item -LiteralPath $destination).Length -ne $lock.model.bytes -or
        (Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash.ToLowerInvariant() -ne $lock.model.sha256) {
        throw 'Pesos existentes inválidos; não foram substituídos'
    }
    Write-Output 'Pesos oficiais íntegros.'
}
& (Join-Path $root 'venv/Scripts/python.exe') --version
Check-Exit 'verificação Python'
Write-Output 'Serviço usa somente biblioteca padrão. Execute build.ps1 após instalar ClangCL >=18 no VS2022.'

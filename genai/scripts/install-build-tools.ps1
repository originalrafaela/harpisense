param([switch]$Install)
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '../..')
$installer = 'C:/Program Files (x86)/Microsoft Visual Studio/Installer/setup.exe'
$vswhere = 'C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe'
$vsPath = [IO.Path]::GetFullPath('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools')
$components = @('Microsoft.VisualStudio.Component.VC.Llvm.Clang', 'Microsoft.VisualStudio.Component.VC.Llvm.ClangToolset')
$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
$isElevated = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$instances = @(& $vswhere -products Microsoft.VisualStudio.Product.BuildTools -version '[17.0,18.0)' -format json | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0) { throw 'Falha ao consultar instalações do VS' }
$instance = $instances | Where-Object { $_.installationPath -eq $vsPath }
if (!$instance) { throw 'Instalação VS2022 usada no CMake não encontrada. Não modificar outra instalação automaticamente.' }
$clang = Join-Path $vsPath 'VC/Tools/Llvm/x64/bin/clang-cl.exe'
$toolset = Join-Path $vsPath 'MSBuild/Microsoft/VC/v170/Platforms/x64/PlatformToolsets/ClangCL/Toolset.props'
$report = [ordered]@{
    checked_at = (Get-Date).ToUniversalTime().ToString('o')
    install_path = $vsPath
    instance_id = $instance.instanceId
    installation_version = $instance.installationVersion
    elevated = $isElevated
    clang_executable_present = (Test-Path -LiteralPath $clang)
    clangcl_toolset_present = (Test-Path -LiteralPath $toolset)
    required_component_ids = $components
    registered_components = @{}
}
foreach ($component in $components) {
    $matches = @(& $vswhere -products Microsoft.VisualStudio.Product.BuildTools -version '[17.0,18.0)' -requires $component -property installationPath)
    if ($LASTEXITCODE -ne 0) { throw "Falha ao consultar $component" }
    $report.registered_components[$component] = [bool]($matches | Where-Object { $_ -eq $vsPath })
}
New-Item -ItemType Directory -Force .local-harpia/results | Out-Null
$report | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 .local-harpia/results/build-prerequisites.json
$report | ConvertTo-Json -Depth 4
if (!$Install) {
    Write-Output 'Somente diagnóstico. Para instalar: abrir PowerShell como administrador e executar este script com -Install.'
    return
}
if ($report.clang_executable_present -and $report.clangcl_toolset_present -and !($report.registered_components.Values -contains $false)) {
    Write-Output 'Os dois componentes já estão instalados; nenhuma alteração realizada.'
    return
}
if (!$isElevated) { throw 'Intervenção administrativa necessária: execute PowerShell como administrador e rode genai/scripts/install-build-tools.ps1 -Install. O script não tenta elevar nem alterar políticas.' }
$arguments = 'modify --installPath "' + $vsPath + '" --add ' + $components[0] + ' --add ' + $components[1] + ' --quiet --norestart'
# Somente adição dos dois componentes e dependências obrigatórias. Sem --force,
# update, remoção de componentes, reinício automático ou alteração de políticas.
$operation = Start-Process -FilePath $installer -ArgumentList $arguments -WindowStyle Hidden -PassThru
Write-Output "Instalador iniciado, PID $($operation.Id). Aguarde seu término; não feche processos de outros trabalhos."
$operation.WaitForExit()
$operation.Refresh()
Write-Output "Installer exit code: $($operation.ExitCode)"
if ($operation.ExitCode -eq 3010) { throw 'Instalação solicita reinício. Não reiniciado automaticamente; combine uma janela com o administrador.' }
if ($operation.ExitCode -ne 0) { throw "Instalador falhou ($($operation.ExitCode)); consulte os logs dd_setup em TEMP antes de repetir." }
Write-Output 'Instalador terminou. Execute novamente sem -Install para validar registro e arquivos.'

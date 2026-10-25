param(
    [string]$VsPath = 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools',
    [ValidateRange(1,2)][int]$Jobs = 1
)
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '../..')
$root = (Get-Location).Path
$runtime = Join-Path $root '.local-harpia/runtime/BitNet'
$clang = Join-Path $VsPath 'VC/Tools/Llvm/x64/bin/clang-cl.exe'
if (!(Test-Path -LiteralPath $clang)) {
    throw 'Falta ClangCL: no Visual Studio Installer/VS2022 adicione C++ Clang Compiler e MSBuild Support for LLVM Toolset. Pode exigir administrador.'
}
$toolset = Join-Path $VsPath 'MSBuild/Microsoft/VC/v170/Platforms/x64/PlatformToolsets/ClangCL/Toolset.props'
if (!(Test-Path -LiteralPath $toolset)) { throw 'Falta MSBuild support for LLVM (clang-cl) toolset no VS2022 selecionado.' }
$python = Join-Path $root '.local-harpia/venv/Scripts/python.exe'
$memory = & $python -m genai.harpia --inspect | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or !$memory) { throw 'Não foi possível verificar RAM antes da compilação' }
New-Item -ItemType Directory -Force .local-harpia/results | Out-Null
$memory | ConvertTo-Json | Set-Content -Encoding utf8 .local-harpia/results/memory-before-build.json
Write-Output ('RAM livre antes do build: {0:N0} MiB; jobs={1}' -f ($memory.available_bytes / 1MB), $Jobs)
if ($memory.available_bytes -lt 1536MB) { throw 'Build adiado: menos de 1536 MiB livres. Nenhum processo externo foi encerrado.' }
& $python -m genai.scripts.patch_runtime
if ($LASTEXITCODE -ne 0) { throw 'Patch FFN recusado; conferir revisão e alterações locais antes de compilar' }
$devShell = Join-Path $VsPath 'Common7/Tools/Microsoft.VisualStudio.DevShell.dll'
Import-Module $devShell
Enter-VsDevShell -VsInstallPath $VsPath -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64'
$cmake = Join-Path $VsPath 'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
$compilerVersion = & $clang --version
if ($LASTEXITCODE -ne 0) { throw 'Clang indisponível' }
Write-Output $compilerVersion
if (($compilerVersion -join ' ') -notmatch 'clang version (\d+)\.' -or [int]$Matches[1] -lt 18) { throw 'BitNet requer Clang >=18' }
# GGUF I2_S já publicado: não converter pesos, não instalar torch/transformers.
& $cmake -S $runtime -B (Join-Path $runtime 'build') -G 'Visual Studio 17 2022' -A x64 -T ClangCL "-DCMAKE_GENERATOR_INSTANCE=$VsPath" -DBITNET_X86_TL2=OFF -DBUILD_SHARED_LIBS=OFF -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF -DLLAMA_BUILD_TOOLS=ON -DLLAMA_BUILD_EXAMPLES=ON -DLLAMA_BUILD_COMMON=ON 2>&1 | Tee-Object -FilePath .local-harpia/results/cmake-configure.txt
if ($LASTEXITCODE -ne 0) { throw 'Configuração CMake falhou; consulte o erro antes de repetir' }
& $cmake --build (Join-Path $runtime 'build') --config Release --target llama-server llama-cli --parallel $Jobs 2>&1 | Tee-Object -FilePath .local-harpia/results/cmake-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Build falhou; consulte diagnóstico, não reinstale automaticamente' }

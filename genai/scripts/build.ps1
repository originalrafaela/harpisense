param([string]$VsPath = 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools')
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '../..')
$root = (Get-Location).Path
$runtime = Join-Path $root '.local-harpia/runtime/BitNet'
$clang = Join-Path $VsPath 'VC/Tools/Llvm/x64/bin/clang-cl.exe'
if (!(Test-Path -LiteralPath $clang)) {
    throw 'Falta ClangCL: no Visual Studio Installer/VS2022 adicione C++ Clang Compiler e MSBuild Support for LLVM Toolset. Pode exigir administrador.'
}
$devShell = Join-Path $VsPath 'Common7/Tools/Microsoft.VisualStudio.DevShell.dll'
Import-Module $devShell
Enter-VsDevShell -VsInstallPath $VsPath -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64'
$cmake = Join-Path $VsPath 'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
& $clang --version
if ($LASTEXITCODE -ne 0) { throw 'Clang indisponível' }
# GGUF I2_S já publicado: não converter pesos, não instalar torch/transformers.
& $cmake -S $runtime -B (Join-Path $runtime 'build') -G 'Visual Studio 17 2022' -A x64 -T ClangCL -DBITNET_X86_TL2=OFF -DLLAMA_BUILD_TOOLS=ON -DLLAMA_BUILD_EXAMPLES=ON -DLLAMA_BUILD_COMMON=ON
if ($LASTEXITCODE -ne 0) { throw 'Configuração CMake falhou; consulte o erro antes de repetir' }
& $cmake --build (Join-Path $runtime 'build') --config Release --target llama-server llama-cli --parallel 2
if ($LASTEXITCODE -ne 0) { throw 'Build falhou; consulte diagnóstico, não reinstale automaticamente' }

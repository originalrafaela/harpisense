param(
    [Parameter(Mandatory=$true)][string]$P06,
    [Parameter(Mandatory=$true)][string]$ContractPython
)
$ErrorActionPreference='Stop'
$project=Split-Path $PSScriptRoot -Parent
Push-Location $project
try {
    New-Item -ItemType Directory -Force test-results | Out-Null
    $env:ZIG_GLOBAL_CACHE_DIR=Join-Path $project '.tools/zig-cache'
    & '.tools/venv/Lib/site-packages/ziglang/zig.exe' c++ -std=c++11 -Wall -Wextra -Werror -I lib/PosteCore/src -I include lib/PosteCore/src/poste_core.cpp tests/core_test.cpp -o test-results/core-test.exe
    if ($LASTEXITCODE -ne 0) { throw 'C++ core compilation failed' }
    $fixtures=& './test-results/core-test.exe'
    if ($LASTEXITCODE -ne 0) { throw 'C++ core tests failed' }
    [IO.File]::WriteAllLines((Join-Path $project 'test-results/firmware.jsonl'),[string[]]$fixtures,[Text.UTF8Encoding]::new($false))
    & $ContractPython tests/verify_contract.py --p06 $P06 --fixtures test-results/firmware.jsonl
    if ($LASTEXITCODE -ne 0) { throw 'P06 firmware fixture validation failed' }
    foreach ($variant in @('OPEN','CLOSED','NO_CA','IP_LITERAL')) {
        $define = '-DTEST_' + $variant
        & '.tools/venv/Lib/site-packages/ziglang/zig.exe' c++ -std=c++11 -Wall -Wextra -Werror $define -include tests/fakes/test_config.h -I tests/fakes -I lib/PosteCore/src -I include lib/PosteCore/src/poste_core.cpp src/communication.cpp tests/communication_test.cpp -o "test-results/communication-$variant.exe"
        if ($LASTEXITCODE -ne 0) { throw "Communication $variant compilation failed" }
        & "./test-results/communication-$variant.exe"
        if ($LASTEXITCODE -ne 0) { throw "Communication $variant tests failed" }
    }
    Write-Output 'PASS: 4 communication orchestration variants with test doubles; no real TLS handshake'
} finally { Pop-Location }

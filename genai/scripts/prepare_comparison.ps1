$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '../..')
$taskRoot = Join-Path (Get-Location) '.local-harpia/comparison'
$taskLock = Get-Content -Raw genai/comparison-artifacts.lock.json | ConvertFrom-Json
New-Item -ItemType Directory -Force $taskRoot | Out-Null
function Get-VerifiedArtifact($taskUrl, $taskPath, $taskBytes, $taskHash) {
    if (!(Test-Path -LiteralPath $taskPath)) {
        Invoke-WebRequest -Uri $taskUrl -OutFile ($taskPath + '.partial')
        if ((Get-Item -LiteralPath ($taskPath + '.partial')).Length -ne $taskBytes -or
            (Get-FileHash -LiteralPath ($taskPath + '.partial') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskHash) {
            throw 'Download does not match pinned size/hash; partial file retained for inspection'
        }
        Move-Item -LiteralPath ($taskPath + '.partial') -Destination $taskPath
    }
    if ((Get-Item -LiteralPath $taskPath).Length -ne $taskBytes -or
        (Get-FileHash -LiteralPath $taskPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskHash) {
        throw 'Existing artifact differs from lock; refusing to replace'
    }
}
$taskModelUrl = 'https://huggingface.co/' + $taskLock.model.repository + '/resolve/' + $taskLock.model.revision + '/' + $taskLock.model.filename
Get-VerifiedArtifact $taskModelUrl (Join-Path $taskRoot $taskLock.model.filename) $taskLock.model.bytes $taskLock.model.sha256
$taskZip = Join-Path $taskRoot 'llama-cpu.zip'
Get-VerifiedArtifact $taskLock.runtime.url $taskZip $taskLock.runtime.bytes $taskLock.runtime.sha256
$taskRuntime = Join-Path $taskRoot 'runtime'
if (!(Test-Path -LiteralPath $taskRuntime)) { Expand-Archive -LiteralPath $taskZip -DestinationPath $taskRuntime }
# Verify extracted files against the pinned archive, including reruns. Do not bless
# locally modified DLLs merely by recording their current hashes.
$taskArchive = [IO.Compression.ZipFile]::OpenRead($taskZip)
$taskArchiveFiles = @{}
try {
    foreach ($taskEntry in $taskArchive.Entries) {
        if (!$taskEntry.Name) { continue }
        $taskTarget = [IO.Path]::GetFullPath((Join-Path $taskRuntime $taskEntry.FullName))
        if (!$taskTarget.StartsWith(([IO.Path]::GetFullPath($taskRuntime) + [IO.Path]::DirectorySeparatorChar), [StringComparison]::OrdinalIgnoreCase)) { throw 'Archive path outside dedicated runtime' }
        $taskStream = $taskEntry.Open()
        $taskDigest = [Security.Cryptography.SHA256]::Create()
        try { $taskExpected = [Convert]::ToHexString($taskDigest.ComputeHash($taskStream)).ToLowerInvariant() }
        finally { $taskStream.Dispose(); $taskDigest.Dispose() }
        if (!(Test-Path -LiteralPath $taskTarget) -or (Get-FileHash -LiteralPath $taskTarget -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskExpected) { throw 'Extracted runtime differs from pinned archive' }
        $taskArchiveFiles[$taskTarget] = $true
    }
    foreach ($taskFile in (Get-ChildItem -LiteralPath $taskRuntime -Recurse -File)) {
        if (!$taskArchiveFiles.ContainsKey($taskFile.FullName)) { throw 'Unexpected file in dedicated runtime folder' }
    }
} finally { $taskArchive.Dispose() }
$taskBaseUrl = 'https://huggingface.co/' + $taskLock.model.base_repository + '/resolve/' + $taskLock.model.base_revision + '/'
foreach ($taskName in @('tokenizer_config.json', 'LICENSE')) {
    $taskTarget = Join-Path $taskRoot $taskName
    if (!(Test-Path -LiteralPath $taskTarget)) { Invoke-WebRequest -Uri ($taskBaseUrl + $taskName) -OutFile $taskTarget }
    $taskExpectedAux = if ($taskName -eq 'LICENSE') { $taskLock.model.license_sha256 } else { $taskLock.model.tokenizer_sha256 }
    if ((Get-FileHash -LiteralPath $taskTarget -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskExpectedAux) { throw 'Official tokenizer/license differs from pinned hash' }
}
$taskExe = Get-ChildItem -LiteralPath $taskRuntime -Recurse -File -Filter llama-server.exe
if (@($taskExe).Count -ne 1) { throw 'Expected exactly one dedicated llama-server.exe' }
$taskVersion = & $taskExe.FullName --version 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) { throw 'Dedicated runtime could not execute' }
$taskFiles = Get-ChildItem -LiteralPath $taskRuntime -Recurse -File | ForEach-Object {
    [ordered]@{path=$_.FullName.Substring($taskRoot.Length+1);bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
}
[ordered]@{runtime_version=$taskVersion.Trim();executable=$taskExe.FullName;files=@($taskFiles);
    tokenizer_sha256=(Get-FileHash -LiteralPath (Join-Path $taskRoot 'tokenizer_config.json') -Algorithm SHA256).Hash.ToLowerInvariant();
    license_sha256=(Get-FileHash -LiteralPath (Join-Path $taskRoot 'LICENSE') -Algorithm SHA256).Hash.ToLowerInvariant()} |
    ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $taskRoot 'installed.json')
Write-Output $taskVersion.Trim()
Write-Output 'Verified comparison artifacts installed locally; no model loaded.'

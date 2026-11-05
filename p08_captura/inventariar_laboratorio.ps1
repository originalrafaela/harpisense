param(
    [Parameter(Mandatory)][string]$RepositoryRoot,
    [Parameter(Mandatory)][string]$CompositionRoot,
    [Parameter(Mandatory)][string]$OutputPath
)
# Inventário local: não executa modelos, captura, serviços ou código da composição.
$ErrorActionPreference = 'Stop'
function Read-Revision([string]$Root, [string]$Revision) {
    $value = & git -c "safe.directory=$Root" -C $Root rev-parse $Revision
    if ($LASTEXITCODE -ne 0) { throw "Falha ao consultar revisão em $Root" }
    return $value
}
if (Test-Path -LiteralPath $OutputPath) { throw 'Saída existente; sobrescrita recusada' }
$reference = Join-Path $RepositoryRoot 'referencias/versão_v2'
$schemaPath = Join-Path $reference '09_Deteccao_Decisao/HarpiSense_Pacote09_Deteccao_Decisao_v2/schemas/feature_schema.json'
$schema = Get-Content -LiteralPath $schemaPath -Raw | ConvertFrom-Json
$origins = Get-Content -LiteralPath (Join-Path $CompositionRoot 'backend/p08_p09/compatibility_sources/ORIGINS.json') -Raw | ConvertFrom-Json
$comparisons = @(
    @('p08_aggregator', (Join-Path $reference '08_Coleta_Evidencias/HarpiSense_Pacote08_Coleta_Evidencias_v2/HarpiSense_Pacote08_Coleta_Evidencias_v2/componentes/edge/edge_features.py'), 'backend/p08_p09/compatibility_sources/edge_features.py'),
    @('p09_validator', (Join-Path $reference '09_Deteccao_Decisao/HarpiSense_Pacote09_Deteccao_Decisao_v2/harpisense_data/windows.py'), 'backend/domain/harpisense_data/windows.py'),
    @('rf', (Join-Path $reference '09_Deteccao_Decisao/HarpiSense_Pacote09_Deteccao_Decisao_v2/harpisense_rf/random_forest.py'), 'backend/domain/harpisense_rf/random_forest.py'),
    @('if', (Join-Path $reference '09_Deteccao_Decisao/HarpiSense_Pacote09_Deteccao_Decisao_v2/harpisense_if/isolation_forest.py'), 'backend/domain/harpisense_if/isolation_forest.py')
) | ForEach-Object {
    $expected = (Get-FileHash -LiteralPath $_[1] -Algorithm SHA256).Hash.ToLowerInvariant()
    $actual = (Get-FileHash -LiteralPath (Join-Path $CompositionRoot $_[2]) -Algorithm SHA256).Hash.ToLowerInvariant()
    [ordered]@{component=$_[0]; reference=$_[1]; composition_path=$_[2]; reference_sha256=$expected; actual_sha256=$actual; byte_equal=($expected -ceq $actual)}
}
$models = @(Get-ChildItem -LiteralPath (Join-Path $CompositionRoot 'local-evidence/detection-composition') -Recurse -File -Filter metadata.json | ForEach-Object {
    $meta = Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json
    $artifact = Join-Path $_.DirectoryName 'model.joblib'
    $artifactHash = if (Test-Path -LiteralPath $artifact) { (Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    [ordered]@{
        path=[IO.Path]::GetRelativePath($CompositionRoot, $_.FullName)
        provenance='synthetic composition fixtures; not operational or laboratory'
        metadata_sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        artifact_sha256=$artifactHash; metadata_hash_matches=($null -ne $artifactHash -and $artifactHash -ceq $meta.artifact_sha256)
        external_trusted_pin_verified=$false
        features=$meta.features; default_order_matches=(($meta.features -join '|') -ceq ($schema.features_default -join '|'))
        feature_schema_version=$meta.feature_schema_version; window_seconds=$meta.window_seconds
        profile=$meta.profile; p08_profile_matches=($meta.profile -ceq 'tcp-observacao')
        versions=$meta.versions; model_version=$meta.model_version; artifact_version=$meta.artifact_version
    }
})
$report = [ordered]@{
    captured_at_utc=[DateTime]::UtcNow.ToString('o')
    p08_head=(Read-Revision ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))) 'HEAD')
    composition_head=(Read-Revision $CompositionRoot 'HEAD')
    reused_composition_base=(Read-Revision $CompositionRoot '7fe8294')
    evidence_type='local source and metadata inventory; no runtime numeric audit'
    schema=$schema; source_comparisons=$comparisons; deployed_source_receipt=$origins
    models=$models; observed_p08_windows=$null; source_coverage='UNKNOWN'
    laboratory_session=$null; inference_performed=$false; p11_write_performed=$false
    status='BLOCKED'; first_collection_blocker='Poste2 ens33 capture permission/linktype receipt missing'
}
$json = ($report | ConvertTo-Json -Depth 20).Replace("`r`n", "`n")
$stream = [IO.File]::Open($OutputPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
try {
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($json + "`n")
    $stream.Write($bytes, 0, $bytes.Length)
} finally { $stream.Dispose() }
Write-Output $OutputPath

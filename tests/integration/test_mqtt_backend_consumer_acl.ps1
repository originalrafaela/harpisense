param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 1883,
    [string]$PublisherPassword = "change-me-iot-lab",
    [Parameter(Mandatory = $true)]
    [string]$BackendConsumerPassword
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$telemetryTopic = "harpisense/v1/telemetry/harpisense.poste.poste-2/environment"
$securityTopic = "harpisense/v1/security/network-event"
$payload = '{"schema_version":"1.0","message_id":"acl-smoke-001","device_id":"harpisense.poste.poste-2","observed_at":"2026-09-17T00:00:00.000Z","sensor_type":"environment","sequence":1,"measurements":{"temperature_c":24.5,"humidity_pct":62.0},"status":{"battery_pct":null,"rssi_dbm":-60}}'

Push-Location mqtt
try {
    $env:HARPISENSE_BACKEND_CONSUMER_PASSWORD = $BackendConsumerPassword
    docker compose --profile init run --rm -e HARPISENSE_BACKEND_CONSUMER_PASSWORD mosquitto-init /mosquitto/config/create-password-file.sh /mosquitto/config/lab-users.example /mosquitto/config/passwords --force
    docker compose up -d mosquitto
}
finally {
    Remove-Item Env:\HARPISENSE_BACKEND_CONSUMER_PASSWORD -ErrorAction SilentlyContinue
    Pop-Location
}

$subJob = Start-Job -ScriptBlock {
    param($HostName, $Port, $Password)
    $output = docker exec harpisense-mosquitto mosquitto_sub -h $HostName -p $Port -u harpisense_backend_consumer -P $Password -t "harpisense/v1/telemetry/#" -C 1 -W 15 2>&1
    [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Output = ($output -join "`n")
    }
} -ArgumentList $HostName, $Port, $BackendConsumerPassword

Start-Sleep -Seconds 2

docker exec harpisense-mosquitto mosquitto_pub -h $HostName -p $Port -u iot_device_lab -P $PublisherPassword -i poste-2 -t $telemetryTopic -m $payload -q 1

$subResult = Receive-Job -Job $subJob -Wait -AutoRemoveJob
if ($subResult.ExitCode -ne 0) {
    throw "Backend consumer subscription to telemetry failed."
}
if ($subResult.Output -notmatch "acl-smoke-001") {
    throw "Backend consumer did not receive the telemetry payload."
}

docker exec harpisense-mosquitto mosquitto_pub -h $HostName -p $Port -u harpisense_backend_consumer -P $BackendConsumerPassword -i harpisense-backend-acl-test -t $telemetryTopic -m $payload -q 1
if ($LASTEXITCODE -eq 0) {
    throw "Backend consumer unexpectedly published telemetry."
}

docker exec harpisense-mosquitto mosquitto_sub -h $HostName -p $Port -u harpisense_backend_consumer -P $BackendConsumerPassword -t "harpisense/v1/security/#" -C 1 -W 3
if ($LASTEXITCODE -eq 0) {
    throw "Backend consumer unexpectedly subscribed to security topics."
}

docker exec harpisense-mosquitto mosquitto_pub -h $HostName -p $Port -u harpisense_backend_consumer -P $BackendConsumerPassword -i harpisense-backend-acl-test -t $securityTopic -m '{}' -q 1
if ($LASTEXITCODE -eq 0) {
    throw "Backend consumer unexpectedly published to security topics."
}

Write-Host "Backend consumer ACL test completed: telemetry read allowed, publish denied, security topics denied."

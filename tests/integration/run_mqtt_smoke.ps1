param(
    [string]$Python = ".\.venv\Scripts\python",
    [string]$HostName = "127.0.0.1",
    [int]$Port = 1883,
    [string]$PublisherPassword = "change-me-iot-lab",
    [string]$SubscriberPassword = "change-me-subscriber-lab"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

Push-Location mqtt
docker compose --profile init run --rm mosquitto-init
docker compose up -d mosquitto
Pop-Location

$subscriberScript = Join-Path $repoRoot "lab\legitimate-traffic\test_subscriber.py"
$publisherScript = Join-Path $repoRoot "lab\legitimate-traffic\simulate_poste.py"

$previousHost = $env:MQTT_HOST
$previousPort = $env:MQTT_PORT
$previousUsername = $env:MQTT_USERNAME
$previousPassword = $env:MQTT_PASSWORD

$env:MQTT_HOST = $HostName
$env:MQTT_PORT = "$Port"
$env:MQTT_USERNAME = "mqtt_test_subscriber"
$env:MQTT_PASSWORD = $SubscriberPassword

try {
    $subscriber = Start-Process -FilePath $Python -ArgumentList @($subscriberScript, "--expected-count", "2", "--timeout", "30") -NoNewWindow -PassThru
}
finally {
    $env:MQTT_HOST = $previousHost
    $env:MQTT_PORT = $previousPort
    $env:MQTT_USERNAME = $previousUsername
    $env:MQTT_PASSWORD = $previousPassword
}

Start-Sleep -Seconds 3

$env:MQTT_HOST = $HostName
$env:MQTT_PORT = "$Port"
$env:MQTT_USERNAME = "iot_device_lab"
$env:MQTT_PASSWORD = $PublisherPassword

try {
    & $Python $publisherScript --device poste-2 --count 2 --interval 1 --exercise-reconnect
    $publisherExitCode = $LASTEXITCODE
}
finally {
    $env:MQTT_HOST = $previousHost
    $env:MQTT_PORT = $previousPort
    $env:MQTT_USERNAME = $previousUsername
    $env:MQTT_PASSWORD = $previousPassword
}

if ($publisherExitCode -ne 0) {
    throw "Publisher failed with exit code $publisherExitCode"
}

$subscriber.WaitForExit(35000) | Out-Null
if (-not $subscriber.HasExited) {
    $subscriber.Kill()
    throw "Subscriber timed out"
}

if ($subscriber.ExitCode -ne 0) {
    throw "Subscriber failed with exit code $($subscriber.ExitCode)"
}

Write-Host "MQTT smoke test completed: simulated publish, receive and client reconnect."

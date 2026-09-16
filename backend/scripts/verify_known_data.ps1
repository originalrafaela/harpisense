param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$Username = "admin",
    [Parameter(Mandatory = $true)]
    [string]$Password
)

$pair = "${Username}:${Password}"
$token = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
$headers = @{
    Authorization = "Basic $token"
    "Content-Type" = "application/json"
}

$telemetry = @{
    schema_version = "1.0"
    message_id = "01JVERIFYTELEMETRY000000000"
    device_id = "harpisense.poste.poste-1"
    observed_at = "2026-09-15T22:30:00.000Z"
    sensor_type = "environment"
    sequence = 42
    measurements = @{
        temperature_c = 24.6
        humidity_pct = 62.1
    }
    status = @{
        battery_pct = $null
        rssi_dbm = -61
    }
} | ConvertTo-Json -Depth 8

$networkEvent = @{
    schema_version = "1.0"
    event_id = "01JVERIFYNETEVENT000000001"
    event_type = "network_event"
    observed_at = "2026-09-15T22:30:01.125Z"
    sensor_id = "harpisense.gateway.edge-1"
    capture = @{
        interface = "eth1"
        direction = "iot_to_test"
        protocol = "tcp"
        src_ip = "192.168.20.31"
        src_port = 49152
        dst_ip = "192.168.20.20"
        dst_port = 1883
        packet_size_bytes = 128
        tcp_flags = "PA"
    }
    mqtt = @{
        present = $true
        message_type = "PUBLISH"
        topic = "harpisense/v1/telemetry/harpisense.poste.poste-1/environment"
        client_id = "poste-1"
    }
    classification = @{
        stage = "raw_capture"
        label = "unknown"
        confidence = $null
    }
} | ConvertTo-Json -Depth 8

Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v1/health"
Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/ingest/telemetry" -Headers $headers -Body $telemetry
Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/ingest/telemetry" -Headers $headers -Body $telemetry
Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/ingest/network-events" -Headers $headers -Body $networkEvent
Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/ingest/network-events" -Headers $headers -Body $networkEvent
Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v1/telemetry?device_id=harpisense.poste.poste-1&limit=10" -Headers $headers
Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v1/network-events?dst_port=1883&limit=10" -Headers $headers

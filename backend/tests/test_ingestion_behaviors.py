from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.exc import SQLAlchemyError


ADMIN_AUTH = ("admin", "secret")
GATEWAY_AUTH = ("harpisense.gateway.edge-1", "gateway-secret")


def telemetry_payload(message_id: str = "msg-001") -> dict:
    return {
        "schema_version": "1.0",
        "message_id": message_id,
        "device_id": "harpisense.poste.alpha",
        "observed_at": "2026-09-17T03:00:00Z",
        "sensor_type": "environment",
        "sequence": None,
        "measurements": {"temperature_c": None, "humidity_pct": 64.2},
        "status": {"battery_v": None},
    }


def network_event_payload(event_id: str = "evt-001") -> dict:
    return {
        "schema_version": "1.0",
        "event_id": event_id,
        "event_type": "network_event",
        "observed_at": "2026-09-17T03:01:00Z",
        "sensor_id": "harpisense.gateway.alpha",
        "capture": {
            "interface": "wlan0",
            "direction": "inbound",
            "protocol": "MQTT",
            "src_ip": "192.168.1.10",
            "src_port": None,
            "dst_ip": "192.168.1.20",
            "dst_port": None,
            "packet_size_bytes": None,
            "tcp_flags": None,
        },
        "mqtt": {
            "present": True,
            "message_type": None,
            "topic": None,
            "client_id": None,
        },
        "classification": {
            "stage": "raw_capture",
            "label": "unknown",
            "confidence": None,
        },
    }


def aggregation_payload() -> dict:
    return {
        "window_seconds": 30,
        "window_start": "2026-09-17T03:01:00Z",
        "window_end": "2026-09-17T03:01:30Z",
        "first_observed_at": "2026-09-17T03:01:01Z",
        "last_observed_at": "2026-09-17T03:01:02Z",
        "packet_count": 4,
        "total_packet_size_bytes": 512,
        "interfaces_observed": ["eth-iot", "eth-test"],
        "expected_interfaces": ["eth-iot", "eth-test"],
        "traversal_verified": True,
        "traversal_reason": "same flow key observed on all configured gateway interfaces",
        "traversal_evidence": {
            "observed_interfaces": ["eth-iot", "eth-test"],
            "required_interfaces": ["eth-iot", "eth-test"],
            "flow_key": {
                "protocol": "TCP",
                "src_ip": "192.168.1.10",
                "src_port": None,
                "dst_ip": "192.168.1.20",
                "dst_port": None,
                "direction": "inbound",
                "mqtt_message_type": None,
                "mqtt_topic": None,
            },
        },
    }


def post_telemetry(client, payload: dict):
    return client.post("/api/v1/ingest/telemetry", json=payload, auth=ADMIN_AUTH)


def post_network_event(client, payload: dict, auth=GATEWAY_AUTH):
    return client.post("/api/v1/ingest/network-events", json=payload, auth=auth)


def test_identical_telemetry_duplicate_returns_202_without_new_record(client):
    first = post_telemetry(client, telemetry_payload())
    second = post_telemetry(client, telemetry_payload())

    assert first.status_code == 202
    assert first.json()["duplicate"] is False
    assert second.status_code == 202
    assert second.json()["duplicate"] is True
    assert second.json()["id"] == first.json()["id"]

    listed = client.get("/api/v1/telemetry", auth=ADMIN_AUTH).json()
    assert len(listed) == 1


def test_same_message_id_with_different_payload_returns_conflict(client):
    payload = telemetry_payload("msg-conflict")
    assert post_telemetry(client, payload).status_code == 202

    changed = telemetry_payload("msg-conflict")
    changed["measurements"] = {"temperature_c": 21.3}
    response = post_telemetry(client, changed)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "identifier_conflict"


def test_concurrent_identical_message_id_is_idempotent(client):
    payload = telemetry_payload("msg-concurrent")

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: post_telemetry(client, payload), range(2)))

    assert sorted(response.status_code for response in responses) == [202, 202]
    assert sorted(response.json()["duplicate"] for response in responses) == [False, True]
    assert len(client.get("/api/v1/telemetry", auth=ADMIN_AUTH).json()) == 1


def test_invalid_payload_returns_validation_error(client):
    payload = telemetry_payload("msg-invalid")
    payload["observed_at"] = "2026-09-17T03:00:00-03:00"

    response = post_telemetry(client, payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_null_values_are_persisted_as_null_not_zero(client):
    telemetry = post_telemetry(client, telemetry_payload("msg-null"))
    network_event = post_network_event(client, network_event_payload("evt-null"))

    assert telemetry.status_code == 202
    assert network_event.status_code == 202

    telemetry_list = client.get("/api/v1/telemetry", auth=ADMIN_AUTH).json()
    event_list = client.get("/api/v1/network-events", auth=ADMIN_AUTH).json()

    assert telemetry_list[0]["sequence"] is None
    assert telemetry_list[0]["measurements"]["temperature_c"] is None
    assert telemetry_list[0]["status"]["battery_v"] is None
    assert event_list[0]["capture"]["src_port"] is None
    assert event_list[0]["capture"]["packet_size_bytes"] is None
    assert event_list[0]["mqtt"]["topic"] is None
    assert event_list[0]["classification"]["confidence"] is None


def test_temporal_filters_and_max_limit_are_enforced(client):
    old_payload = telemetry_payload("msg-old")
    old_payload["observed_at"] = "2026-09-17T01:00:00Z"
    new_payload = telemetry_payload("msg-new")
    new_payload["observed_at"] = "2026-09-17T03:00:00Z"
    assert post_telemetry(client, old_payload).status_code == 202
    assert post_telemetry(client, new_payload).status_code == 202

    filtered = client.get(
        "/api/v1/telemetry",
        params={"observed_from": "2026-09-17T02:00:00Z", "limit": 1},
        auth=ADMIN_AUTH,
    )
    too_many = client.get("/api/v1/telemetry", params={"limit": 501}, auth=ADMIN_AUTH)

    assert filtered.status_code == 200
    assert [item["message_id"] for item in filtered.json()] == ["msg-new"]
    assert too_many.status_code == 422


def test_event_id_conflict_is_detected(client):
    payload = network_event_payload("evt-conflict")
    assert post_network_event(client, payload).status_code == 202

    changed = network_event_payload("evt-conflict")
    changed["capture"]["dst_ip"] = "192.168.1.99"
    response = post_network_event(client, changed)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "identifier_conflict"


def test_admin_credentials_are_not_accepted_for_network_event_ingestion(client):
    response = post_network_event(client, network_event_payload("evt-admin-denied"), auth=ADMIN_AUTH)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_error"


def test_missing_gateway_credentials_return_unauthorized(client):
    response = client.post("/api/v1/ingest/network-events", json=network_event_payload("evt-missing-auth"))

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Basic"
    assert response.json()["error"]["code"] == "authentication_error"


def test_gateway_credentials_are_not_accepted_for_admin_endpoints(client):
    telemetry = client.post("/api/v1/ingest/telemetry", json=telemetry_payload("msg-gateway-denied"), auth=GATEWAY_AUTH)
    query = client.get("/api/v1/network-events", auth=GATEWAY_AUTH)

    assert telemetry.status_code == 401
    assert query.status_code == 401


def test_missing_gateway_credentials_return_service_unavailable(client):
    from app.core.config import settings

    settings.gateway_username = None
    settings.gateway_password = None

    response = post_network_event(client, network_event_payload("evt-missing-gateway-config"))

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "configuration_error"


def test_network_event_with_aggregation_is_accepted_persisted_and_idempotent(client):
    payload = network_event_payload("evt-aggregation")
    payload["aggregation"] = aggregation_payload()

    first = post_network_event(client, payload)
    second = post_network_event(client, payload)
    listed = client.get("/api/v1/network-events", auth=ADMIN_AUTH).json()

    assert first.status_code == 202
    assert first.json()["duplicate"] is False
    assert second.status_code == 202
    assert second.json()["duplicate"] is True
    assert listed[0]["aggregation"]["packet_count"] == 4
    assert listed[0]["aggregation"]["traversal_evidence"]["flow_key"]["protocol"] == "tcp"


def test_invalid_aggregation_returns_validation_error(client):
    payload = network_event_payload("evt-bad-aggregation")
    payload["aggregation"] = aggregation_payload()
    payload["aggregation"]["packet_count"] = 0

    response = post_network_event(client, payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_network_window_is_not_accepted_by_current_ingestion(client):
    payload = network_event_payload("evt-network-window")
    payload["event_type"] = "network_window"

    response = post_network_event(client, payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_database_failure_does_not_return_accepted(client, monkeypatch):
    from app.api.v1.routes import ingest

    def fail_ingest(*args, **kwargs):
        raise SQLAlchemyError("forced failure")

    monkeypatch.setattr(ingest, "ingest_telemetry", fail_ingest)

    response = post_telemetry(client, telemetry_payload("msg-db-failure"))

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_error"

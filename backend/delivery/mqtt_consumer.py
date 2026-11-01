"""Operational callbacks for the existing authenticated client.

No network bootstrap: the installer retains the client, credentials, broker,
TLS configuration and PostgresStore. Binding never connects or starts a loop.
"""
from .mqtt_input import TelemetryInput
from .projections import Record


def bind_consumer(client, store, audit, *, poste1_enabled=False,
                  record_factory=Record, log=print):
    adapter = TelemetryInput(store, audit, poste1_enabled=poste1_enabled,
                             record_factory=record_factory)

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            log("Falha MQTT", flush=True)
            return
        adapter.subscribe(client)
        log("MQTT conectado e autenticado", flush=True)

    def on_message(client, userdata, message):
        try:
            outcome = adapter.on_message(client, userdata, message)
            log(f"Ingestão MQTT: {outcome}", flush=True)
            return outcome
        except Exception as exc:
            log(f"Erro operacional MQTT: {type(exc).__name__}", flush=True)
            return "operational_error"

    client.on_connect = on_connect
    client.on_message = on_message
    return adapter

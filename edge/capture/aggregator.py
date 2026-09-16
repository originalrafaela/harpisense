from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from edge.capture.events import PacketObservation, build_network_event, datetime_to_iso


class WindowAggregator:
    def __init__(
        self,
        *,
        sensor_id: str,
        window_seconds: int = 30,
        expected_interfaces: Iterable[str] | None = None,
    ) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than zero")
        self.sensor_id = sensor_id
        self.window_seconds = window_seconds
        self.expected_interfaces = set(expected_interfaces or [])

    def aggregate(self, observations: Iterable[PacketObservation]) -> list[dict[str, Any]]:
        buckets: dict[tuple[Any, ...], list[PacketObservation]] = defaultdict(list)
        for observation in observations:
            buckets[(self._window_start(observation.observed_at), *observation.flow_key)].append(observation)

        events = []
        for (window_start, *_), items in sorted(buckets.items(), key=lambda item: (item[0][0], repr(item[0][1:]))):
            events.append(self._event_for_bucket(window_start, items))
        return events

    def _event_for_bucket(self, window_start: datetime, items: list[PacketObservation]) -> dict[str, Any]:
        ordered = sorted(items, key=lambda item: item.observed_at)
        first = ordered[0]
        interfaces = sorted({item.interface for item in ordered})
        packet_count = len(ordered)
        total_bytes = sum(item.packet_size_bytes for item in ordered)
        window_end = window_start + timedelta(seconds=self.window_seconds)
        traversal_verified = self._traversal_verified(interfaces)
        traversal_evidence = self._traversal_evidence(first, interfaces)

        aggregate_observation = PacketObservation(
            observed_at=first.observed_at,
            interface=",".join(interfaces),
            direction=first.direction,
            protocol=first.protocol,
            src_ip=first.src_ip,
            src_port=first.src_port,
            dst_ip=first.dst_ip,
            dst_port=first.dst_port,
            packet_size_bytes=total_bytes,
            tcp_flags=first.tcp_flags,
            mqtt_present=first.mqtt_present,
            mqtt_message_type=first.mqtt_message_type,
            mqtt_topic=first.mqtt_topic,
            mqtt_client_id=first.mqtt_client_id,
        )

        return build_network_event(
            aggregate_observation,
            self.sensor_id,
            aggregation={
                "window_seconds": self.window_seconds,
                "window_start": datetime_to_iso(window_start),
                "window_end": datetime_to_iso(window_end),
                "first_observed_at": datetime_to_iso(ordered[0].observed_at),
                "last_observed_at": datetime_to_iso(ordered[-1].observed_at),
                "packet_count": packet_count,
                "total_packet_size_bytes": total_bytes,
                "interfaces_observed": interfaces,
                "expected_interfaces": sorted(self.expected_interfaces),
                "traversal_verified": traversal_verified,
                "traversal_evidence": traversal_evidence,
                "traversal_reason": self._traversal_reason(interfaces, traversal_verified),
            },
        )

    def _window_start(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        value = value.astimezone(timezone.utc)
        epoch = int(value.timestamp())
        bucket_epoch = epoch - (epoch % self.window_seconds)
        return datetime.fromtimestamp(bucket_epoch, tz=timezone.utc)

    def _traversal_verified(self, interfaces: list[str]) -> bool:
        if len(self.expected_interfaces) >= 2:
            return self.expected_interfaces.issubset(set(interfaces))
        return len(interfaces) >= 2

    def _traversal_reason(self, interfaces: list[str], verified: bool) -> str:
        if verified:
            return "same flow key observed on all configured gateway interfaces"
        if len(self.expected_interfaces) >= 2:
            missing = sorted(self.expected_interfaces.difference(interfaces))
            return f"missing configured gateway interface observation: {','.join(missing)}"
        return "at least two gateway interfaces are required to prove traversal"

    def _traversal_evidence(self, observation: PacketObservation, interfaces: list[str]) -> dict[str, Any]:
        return {
            "observed_interfaces": interfaces,
            "required_interfaces": sorted(self.expected_interfaces),
            "flow_key": {
                "protocol": observation.protocol,
                "src_ip": observation.src_ip,
                "src_port": observation.src_port,
                "dst_ip": observation.dst_ip,
                "dst_port": observation.dst_port,
                "direction": observation.direction,
                "mqtt_message_type": observation.mqtt_message_type,
                "mqtt_topic": observation.mqtt_topic,
            },
        }

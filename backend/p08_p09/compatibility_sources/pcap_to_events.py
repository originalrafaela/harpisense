
#!/usr/bin/env python3
"""HarpiSense P08 - Conversor PCAP classico para network_event JSONL.

Escopo inicial:
- PCAP classico (nao PCAPNG)
- Ethernet sem VLAN
- IPv4/TCP sem fragmentacao
- Somente biblioteca padrao
- Falha fechada diante de dados invalidos ou nao suportados
"""

import argparse
import hashlib
import ipaddress
import json
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path


MAGIC = {
    b"\xd4\xc3\xb2\xa1": ("<", 1_000_000),
    b"\xa1\xb2\xc3\xd4": (">", 1_000_000),
    b"\x4d\x3c\xb2\xa1": ("<", 1_000_000_000),
    b"\xa1\xb2\x3c\x4d": (">", 1_000_000_000),
}

FLAG_BITS = (
    (0x001, "F"),
    (0x002, "S"),
    (0x004, "R"),
    (0x008, "P"),
    (0x010, "A"),
    (0x020, "U"),
    (0x040, "E"),
    (0x080, "C"),
    (0x100, "N"),
)


class ConversionError(Exception):
    pass


def read_exact(handle, size, label):
    data = handle.read(size)
    if len(data) != size:
        raise ConversionError(f"{label}: dados truncados")
    return data


def parse_tcp_ipv4(frame):
    if len(frame) < 14:
        raise ConversionError("quadro Ethernet truncado")

    ether_type = struct.unpack_from("!H", frame, 12)[0]
    if ether_type != 0x0800:
        raise ConversionError(
            f"EtherType nao suportado: 0x{ether_type:04x}"
        )

    ip = frame[14:]
    if len(ip) < 20:
        raise ConversionError("cabecalho IPv4 truncado")

    version = ip[0] >> 4
    ihl = (ip[0] & 0x0F) * 4

    if version != 4 or ihl < 20 or len(ip) < ihl:
        raise ConversionError("cabecalho IPv4 invalido")

    total_length = struct.unpack_from("!H", ip, 2)[0]
    if total_length < ihl or len(ip) < total_length:
        raise ConversionError("pacote IPv4 invalido ou truncado")

    fragment = struct.unpack_from("!H", ip, 6)[0]
    if fragment & 0x3FFF:
        raise ConversionError("fragmentacao IPv4 nao suportada")

    if ip[9] != 6:
        raise ConversionError("protocolo IP nao TCP")

    if total_length < ihl + 20:
        raise ConversionError("cabecalho TCP ausente")

    tcp = ip[ihl:total_length]
    src_port, dst_port = struct.unpack_from("!HH", tcp, 0)

    tcp_header_length = (tcp[12] >> 4) * 4
    if tcp_header_length < 20 or len(tcp) < tcp_header_length:
        raise ConversionError("cabecalho TCP invalido ou truncado")

    tcp_flags = ((tcp[12] & 0x01) << 8) | tcp[13]
    flags = "".join(
        letter for bit, letter in FLAG_BITS if tcp_flags & bit
    )

    return {
        "protocol": "tcp",
        "src_ip": str(ipaddress.IPv4Address(ip[12:16])),
        "dst_ip": str(ipaddress.IPv4Address(ip[16:20])),
        "src_port": src_port,
        "dst_port": dst_port,
        "tcp_flags": flags,
        "packet_size_bytes": total_length,
    }


def convert(path, sensor_id, interface):
    if not sensor_id or not interface:
        raise ConversionError("sensor_id e interface obrigatorios")

    events = []
    stats = {
        "records": 0,
        "converted": 0,
        "rejected": 0,
        "reasons": {},
    }

    with path.open("rb") as handle:
        header = read_exact(handle, 24, "cabecalho PCAP")
        magic = header[:4]

        if magic not in MAGIC:
            raise ConversionError("formato PCAP nao suportado")

        endian, precision = MAGIC[magic]
        major, minor, _, _, snaplen, linktype = struct.unpack(
            endian + "HHiIII", header[4:]
        )

        if (major, minor) != (2, 4):
            raise ConversionError("versao PCAP nao suportada")
        if linktype != 1:
            raise ConversionError("link-layer nao Ethernet")
        if snaplen < 14:
            raise ConversionError("snaplen invalido")

        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()

        while True:
            record_header = handle.read(16)
            if not record_header:
                break
            if len(record_header) != 16:
                raise ConversionError("cabecalho de registro truncado")

            seconds, fraction, captured_len, original_len = (
                struct.unpack(endian + "IIII", record_header)
            )

            index = stats["records"]
            stats["records"] += 1

            if fraction >= precision:
                raise ConversionError(
                    f"registro {index}: timestamp invalido"
                )
            if (
                captured_len > snaplen
                or captured_len > original_len
                or original_len == 0
            ):
                raise ConversionError(
                    f"registro {index}: comprimentos invalidos"
                )

            frame = read_exact(
                handle, captured_len, f"registro {index}"
            )

            if captured_len != original_len:
                raise ConversionError(
                    f"registro {index}: captura truncada"
                )

            try:
                capture = parse_tcp_ipv4(frame)
            except ConversionError as exc:
                reason = str(exc)
                stats["rejected"] += 1
                stats["reasons"][reason] = (
                    stats["reasons"].get(reason, 0) + 1
                )
                continue

            timestamp_us = (
                seconds * 1_000_000
                + fraction * 1_000_000 // precision
            )
            observed_at = (
                datetime.fromtimestamp(
                    timestamp_us / 1_000_000,
                    tz=timezone.utc,
                )
                .isoformat(timespec="microseconds")
                .replace("+00:00", "Z")
            )

            event_id = hashlib.sha256(
                f"{file_hash}:{index}".encode("ascii")
            ).hexdigest()

            events.append({
                "event_type": "network_event",
                "record_kind": "raw_event",
                "schema_version": "1.0",
                "event_id": event_id,
                "sensor_id": sensor_id,
                "observed_at": observed_at,
                "capture": {
                    "interface": interface,
                    **capture,
                },
            })
            stats["converted"] += 1

    return events, stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pcap", type=Path)
    parser.add_argument("--sensor-id", required=True)
    parser.add_argument("--interface", required=True)
    args = parser.parse_args()

    try:
        events, stats = convert(
            args.pcap, args.sensor_id, args.interface
        )
    except (ConversionError, OSError, OverflowError, ValueError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    for event in events:
        print(
            json.dumps(
                event,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )
        )

    print(
        "RESUMO " + json.dumps(stats, ensure_ascii=False),
        file=sys.stderr,
    )

    if stats["rejected"]:
        print(
            "AVISO: existem registros nao convertidos; "
            "nao declarar coleta completa.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())

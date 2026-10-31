"""Auditoria offline do contrato RF/IF compartilhado; nunca carrega modelos."""
import argparse
import json
import math
from pathlib import Path

from coverage_evidence import parse_time, sha256_file


def audit(integration, session, schema, model_metadata=None):
    errors = []
    windows = integration.get("aggregation", {}).get("windows", [])
    if not windows:
        errors.append("Nenhuma janela produzida; compatibilidade não demonstrada")
    seen = set()
    start = parse_time(session["capture_effective_started_at"])
    end = parse_time(session["capture_effective_ended_at"])
    for index, row in enumerate(windows):
        reasons = []
        for field in schema["metadata_required"] + schema["metadata_required_operational"] + schema["group_by"]:
            if row.get(field) is None or row.get(field) == "":
                reasons.append("Metadado ausente: " + field)
        wid = row.get("window_id")
        if not isinstance(wid, str) or not wid or wid in seen:
            reasons.append("ID ausente ou duplicado")
        seen.add(wid)
        expected = {"collection_session_id": session["session_id"],
                    "sensor_id": session["sensor_id"],
                    "traffic_profile": session["traffic_profile"],
                    "src_ip": session["source_ip"], "dst_ip": session["destination_ip"],
                    "feature_schema_version": schema["version"],
                    "window_seconds": schema["window_seconds_default"]}
        for key, value in expected.items():
            if row.get(key) != value:
                reasons.append("Identidade/contrato divergente: " + key)
        try:
            left, right = parse_time(row["window_start"]), parse_time(row["window_end"])
            if not start <= left < right <= end or (right-left).total_seconds() != row["window_seconds"]:
                reasons.append("Janela parcial, fora do período efetivo ou duração divergente")
        except (ValueError, TypeError, KeyError):
            reasons.append("Limites de janela inválidos")
        features = list(schema["features_default"])
        if model_metadata:
            features = model_metadata["features"]
            if len(features) != len(set(features)) or not features:
                reasons.append("Ordem de features do artefato inválida")
            if model_metadata.get("profile") != row.get("traffic_profile") or model_metadata.get("window_seconds") != row.get("window_seconds"):
                reasons.append("Perfil/duração incompatível com artefato")
        for name in features:
            value = row.get(name)
            if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
                reasons.append("Feature ausente ou inválida: " + name)
        errors.extend(f"window[{index}]: {reason}" for reason in reasons)
    return {"structural_compatibility": "PASS" if not errors else "BLOCKED",
            "model_compatibility": ("PASS" if not errors else "BLOCKED") if model_metadata else "NOT_VERIFIED",
            "windows_checked": len(windows), "errors": errors,
            "authorized_for_inference": False, "authorized_for_ips": False,
            "log_counts": {}, "limitations": ["Estrutura não prova cálculo numérico, cobertura ou autoria."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--integration", type=Path, required=True)
    parser.add_argument("--session-report", type=Path, required=True)
    parser.add_argument("--feature-schema", type=Path, required=True)
    parser.add_argument("--model-metadata", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    read = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = audit(read(args.integration), read(args.session_report), read(args.feature_schema),
                   read(args.model_metadata) if args.model_metadata else None)
    result["input_sha256"] = {str(p): sha256_file(p) for p in
                              (args.integration, args.session_report, args.feature_schema)}
    if args.model_metadata:
        result["input_sha256"][str(args.model_metadata)] = sha256_file(args.model_metadata)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
    return 0 if result["structural_compatibility"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

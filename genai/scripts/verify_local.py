"""Smoke real do serviço SEM modelo; mede somente wrapper/fallback/encerramento."""
import ctypes
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

from genai.harpia.client import Client
from genai.harpia.runtime import available_memory


def working_set(process):
    if os.name != "nt":
        return None
    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
            (name, ctypes.c_size_t) for name in ("peak_ws", "ws", "peak_paged", "paged", "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile")]
    value = Counters()
    value.cb = ctypes.sizeof(value)
    if not ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(int(process._handle)), ctypes.byref(value), value.cb):
        return None
    return {"working_set_bytes": value.ws, "peak_working_set_bytes": value.peak_ws}


def cpu_seconds(process):
    if os.name != "nt":
        return None
    values = [ctypes.c_ulonglong() for _ in range(4)]
    if ctypes.windll.kernel32.GetProcessTimes(ctypes.c_void_p(int(process._handle)), *(ctypes.byref(v) for v in values)):
        return (values[2].value + values[3].value) / 10000000
    return None


def main():
    folder = Path(".local-harpia/results")
    folder.mkdir(parents=True, exist_ok=True)
    config = json.loads(Path("genai/config.example.json").read_text())
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        config["port"] = sock.getsockname()[1]
    config_path = folder / "smoke-config.json"
    config_path.write_text(json.dumps(config))
    report = {"kind": "real_local_wrapper_without_model", "memory_before": available_memory()}
    with open(folder / "smoke-service.log", "w", encoding="utf-8") as logs:
        # Windows venv python.exe may be a redirector process. Spawn the dedicated
        # base interpreter directly (service is stdlib-only), so counters refer
        # to the interpreter running HarpIA rather than its small launcher.
        interpreter = getattr(sys, "_base_executable", sys.executable)
        report["interpreter"] = interpreter
        process = subprocess.Popen([interpreter, "-m", "genai.harpia", "--config", str(config_path), "--no-model", "--stdin-control"],
                                   stdin=subprocess.PIPE, stdout=logs, stderr=logs, text=True,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        url = f"http://127.0.0.1:{config['port']}"
        headers = {}
        if os.getenv("HARPIA_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["HARPIA_TOKEN"]
        def get(path):
            try:
                with urllib.request.urlopen(urllib.request.Request(url + path, headers=headers), timeout=1) as response:
                    return response.status, json.loads(response.read())
            except urllib.error.HTTPError as exc:
                return exc.code, json.loads(exc.read())
        started = time.monotonic()
        try:
            for _ in range(50):
                try:
                    report["health"] = get("/health")
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("service failed to start")
            report["wrapper_start_seconds"] = time.monotonic() - started
            report["readiness"] = get("/ready")
            begin = time.monotonic()
            result = Client(url).explanation({"incident_id": "synthetic-smoke-001", "revision": 1, "facts": {}})
            report["fallback_seconds"] = time.monotonic() - begin
            report["explanation"] = result
            report["service_memory"] = working_set(process)
            report["service_cpu_seconds"] = cpu_seconds(process)
            assert report["health"][0] == 200
            assert report["readiness"][0] == 503
            assert result["source"] == "deterministic_fallback"
        finally:
            process.stdin.write("stop\n")
            process.stdin.flush()
            process.stdin.close()
            try:
                report["exit_code"] = process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise RuntimeError("graceful shutdown failed")
        report["shutdown_verified"] = report["exit_code"] == 0
        with socket.socket() as sock:
            report["port_closed"] = sock.connect_ex(("127.0.0.1", config["port"])) != 0
        assert report["shutdown_verified"] and report["port_closed"]
    (folder / "local-smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

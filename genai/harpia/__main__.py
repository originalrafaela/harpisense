import argparse
import json
import logging
import os
from pathlib import Path
import signal
import sys
import threading

from .runtime import Runtime, available_memory
from .server import LocalServer


def main():
    parser = argparse.ArgumentParser(description="HarpIA loopback, CPU, sem ferramentas")
    parser.add_argument("--config", default="genai/config.example.json")
    parser.add_argument("--no-model", action="store_true", help="serviço vivo, prontidão 503; teste de indisponibilidade")
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--stdin-control", action="store_true", help="encerrar ao receber stop na entrada padrão")
    args = parser.parse_args()
    if args.inspect:
        print(json.dumps(available_memory()))
        return
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    runtime = Runtime(config["runtime_url"], config["inference_timeout_seconds"])
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    # Bind before loading to reject an occupied integration port cheaply.
    server = LocalServer((config["host"], config["port"]), runtime, os.getenv("HARPIA_TOKEN", ""))
    def stop(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    if args.stdin_control:
        def read_control():
            for line in sys.stdin:
                if line.strip() == "stop":
                    stop()
                    break
        threading.Thread(target=read_control, daemon=True).start()
    try:
        if not args.no_model:
            ready = runtime.start(config["runtime_executable"], config["model_path"], config["logs_dir"],
                                  config["threads"], config["context_tokens"], config["reserve_memory_mb"])
            logging.info("runtime ready=%s reason=%s load_seconds=%s", ready, runtime.error, runtime.load_seconds)
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        runtime.stop()


if __name__ == "__main__":
    main()

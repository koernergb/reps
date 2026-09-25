"""Local development launcher: API (with reload) plus the execution worker.

Both children receive SIGINT/SIGTERM when this process stops, so Ctrl-C shuts everything down.
"""

from __future__ import annotations

import signal
import subprocess
import sys
import time

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    api = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--reload",
            "--host",
            settings.api_host,
            "--port",
            str(settings.api_port),
        ]
    )
    worker = subprocess.Popen([sys.executable, "-m", "app.worker"])
    children = [api, worker]

    def stop(signum: int, frame: object) -> None:
        for child in children:
            if child.poll() is None:
                child.send_signal(signal.SIGTERM)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
    finally:
        stop(signal.SIGTERM, None)
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()


if __name__ == "__main__":
    main()

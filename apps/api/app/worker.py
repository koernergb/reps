"""Execution worker: claims queued jobs and runs them in the sandbox.

Run with `pnpm dev:worker` (or `python -m app.worker`). The API never executes learner code; it
only records jobs. Multiple workers may run concurrently; claiming is an atomic UPDATE.
"""

from __future__ import annotations

import signal
import threading
import time
from types import FrameType

import structlog

from app.config import get_settings
from app.db import create_database_engine, create_session_factory
from app.execution.service import build_backend, process_available_jobs, recover_stale_running_jobs
from app.logging import configure_logging
from app.worker_hooks import register_hooks

logger = structlog.get_logger()
POLL_INTERVAL_S = 0.2


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    register_hooks()
    engine = create_database_engine()
    session_factory = create_session_factory(engine)
    backend = build_backend(settings)
    stop = threading.Event()

    def request_stop(signum: int, frame: FrameType | None) -> None:
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    with session_factory() as session:
        recovered = recover_stale_running_jobs(session, older_than_s=0)
    logger.info(
        "execution_worker_started",
        backend=backend.name,
        concurrency=settings.worker_concurrency,
        recovered_jobs=recovered,
    )

    def loop() -> None:
        while not stop.is_set():
            try:
                processed = process_available_jobs(session_factory, backend, limit=1)
            except Exception:
                logger.exception("execution_worker_iteration_failed")
                processed = 0
            if not processed:
                stop.wait(POLL_INTERVAL_S)

    threads = [
        threading.Thread(target=loop, name=f"exec-worker-{index}", daemon=True)
        for index in range(settings.worker_concurrency)
    ]
    for thread in threads:
        thread.start()
    while not stop.is_set():
        time.sleep(0.5)
    for thread in threads:
        thread.join(timeout=10)
    engine.dispose()
    logger.info("execution_worker_stopped")


if __name__ == "__main__":
    main()

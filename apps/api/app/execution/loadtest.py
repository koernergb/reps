"""Sandbox latency/concurrency baseline.

    python -m app.execution.loadtest --jobs 24 --concurrency 4

Runs a passing reference submission (visible + hidden tests) through the Docker backend.
"""

from __future__ import annotations

import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from app.config import get_settings
from app.corpus.loader import get_corpus
from app.corpus.validate import spec_for
from app.execution.backends import DockerSandboxBackend
from app.execution.evaluate import execute_tests
from app.execution.service import limits_for


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=24)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--problem", default="pair-sum-indices")
    args = parser.parse_args()
    settings = get_settings()
    loaded = get_corpus().problem(args.problem)
    backend = DockerSandboxBackend(settings.sandbox_image)
    limits = limits_for(settings, loaded.definition.per_test_timeout_s)

    def one(_: int) -> tuple[float, str]:
        started = time.perf_counter()
        outcome = execute_tests(
            backend,
            spec_for(loaded),
            loaded.definition.reference_solution,
            loaded.visible_tests,
            loaded.hidden_tests,
            limits,
        )
        return time.perf_counter() - started, outcome.verdict

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(one, range(args.jobs)))
    wall = time.perf_counter() - started
    latencies = sorted(latency for latency, _ in results)
    verdicts = {verdict for _, verdict in results}
    p95 = latencies[max(0, int(len(latencies) * 0.95) - 1)]
    print(
        f"jobs={args.jobs} concurrency={args.concurrency} verdicts={sorted(verdicts)} "
        f"p50={statistics.median(latencies):.2f}s p95={p95:.2f}s max={latencies[-1]:.2f}s "
        f"throughput={args.jobs / wall:.2f} jobs/s"
    )


if __name__ == "__main__":
    main()

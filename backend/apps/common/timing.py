"""Lightweight step timing for locating latency in request and worker paths.

Log lines look like ``step=smtp_connect ms=812.4 mail_log=42`` on the ``erp.timing`` logger.
Never pass secrets (tokens, passwords, links) as fields.
"""

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

logger = logging.getLogger("erp.timing")


def log_step(step: str, elapsed_ms: float, outcome: str = "ok", **fields) -> None:
    extra = "".join(f" {key}={value}" for key, value in fields.items())
    logger.info("step=%s ms=%.1f outcome=%s%s", step, elapsed_ms, outcome, extra)


@contextmanager
def timed(step: str, **fields) -> Iterator[None]:
    start = time.perf_counter()
    outcome = "ok"
    try:
        yield
    except BaseException:
        outcome = "error"
        raise
    finally:
        log_step(step, (time.perf_counter() - start) * 1000, outcome, **fields)

from __future__ import annotations

import logging
import signal

from .db import close_pool, open_pool
from .logging_setup import configure_logging
from .settings import get_settings
from .worker.scheduler import build_scheduler

log = logging.getLogger(__name__)


def run() -> None:
    s = get_settings()
    configure_logging(s.log_level)
    open_pool()
    sched = build_scheduler()

    def _stop(_signum, _frame):
        log.info("worker.shutdown.signal")
        sched.shutdown(wait=False)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    log.info("worker.startup")
    try:
        sched.start()
    finally:
        close_pool()
        log.info("worker.shutdown")


if __name__ == "__main__":
    run()

from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from ..settings import get_settings

log = logging.getLogger(__name__)


def heartbeat() -> None:
    log.info("worker.heartbeat")


def build_scheduler() -> BlockingScheduler:
    s = get_settings()
    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(heartbeat, "interval", seconds=s.worker_interval_seconds, id="heartbeat")
    return sched

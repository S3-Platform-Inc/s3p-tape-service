from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from ..settings import get_settings
from .generator import tick as generator_tick

log = logging.getLogger(__name__)


def heartbeat() -> None:
    log.info("worker.heartbeat")


def generator_job() -> None:
    generator_tick()


def build_scheduler() -> BlockingScheduler:
    s = get_settings()
    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(
        heartbeat, "interval",
        seconds=s.worker_interval_seconds, id="heartbeat",
    )
    sched.add_job(
        generator_job, "interval",
        seconds=s.worker_interval_seconds, id="generator",
        max_instances=1, coalesce=True,
    )
    return sched

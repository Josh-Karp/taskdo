"""APScheduler wrapper for app jobs."""

from __future__ import annotations

import os
from collections.abc import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


class AppScheduler:
    """Wrapper around APScheduler with registration helper."""

    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler()

    @property
    def running(self) -> bool:
        return self._scheduler.running

    def start(self) -> None:
        self._scheduler.start()

    def shutdown(self, wait: bool = False) -> None:
        self._scheduler.shutdown(wait=wait)

    def register_job(self, job_id: str, func: Callable, trigger) -> None:
        self._scheduler.add_job(func=func, trigger=trigger, id=job_id, replace_existing=True)

    def register_sync_job(self, func: Callable) -> None:
        cron_time = os.getenv("CRON_SYNC_TIME", "07:45")
        hour, minute = self._parse_hhmm(cron_time)
        self.register_job(
            job_id="odoo_sync",
            func=func,
            trigger=CronTrigger(hour=hour, minute=minute),
        )

    @staticmethod
    def _parse_hhmm(value: str) -> tuple[int, int]:
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError("CRON_SYNC_TIME must use HH:MM format")
        hour = int(parts[0])
        minute = int(parts[1])
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("CRON_SYNC_TIME must be a valid HH:MM value")
        return hour, minute


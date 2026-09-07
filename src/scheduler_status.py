"""Helpers for reading Windows Task Scheduler status."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


TASK_NAME = "SUUMOPriceTrackerDaily"


@dataclass(frozen=True)
class ScheduleStatus:
    installed: bool
    task_name: str
    next_run: str | None
    last_run: str | None
    last_result: str | None
    status: str | None
    raw: str


def query_schedule_status(task_name: str = TASK_NAME) -> ScheduleStatus:
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", task_name, "/V", "/FO", "LIST"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    raw = (result.stdout or result.stderr or "").strip()
    if result.returncode != 0:
        return ScheduleStatus(
            installed=False,
            task_name=task_name,
            next_run=None,
            last_run=None,
            last_result=None,
            status=None,
            raw=raw,
        )

    fields: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()

    return ScheduleStatus(
        installed=True,
        task_name=task_name,
        next_run=fields.get("次回の実行時刻") or fields.get("Next Run Time"),
        last_run=fields.get("前回の実行時刻") or fields.get("Last Run Time"),
        last_result=fields.get("前回の結果") or fields.get("Last Result"),
        status=fields.get("状態") or fields.get("Status"),
        raw=raw,
    )

"""Install / show / remove the Windows daily scrape scheduled task."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASK_NAME = "SUUMOPriceTrackerDaily"
BAT_PATH = ROOT / "scripts" / "run_daily.bat"
DEFAULT_TIME = "06:30"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def install(time: str = DEFAULT_TIME) -> int:
    if not BAT_PATH.exists():
        print(f"missing bat: {BAT_PATH}", file=sys.stderr)
        return 1
    # /RL HIGHEST helps when network access is restricted under some policies;
    # /F overwrites existing task.
    cmd = [
        "schtasks",
        "/Create",
        "/TN",
        TASK_NAME,
        "/TR",
        str(BAT_PATH),
        "/SC",
        "DAILY",
        "/ST",
        time,
        "/RL",
        "LIMITED",
        "/F",
    ]
    result = _run(cmd)
    print(result.stdout.strip() or result.stderr.strip())
    return result.returncode


def status() -> int:
    result = _run(["schtasks", "/Query", "/TN", TASK_NAME, "/V", "/FO", "LIST"])
    text = result.stdout.strip() or result.stderr.strip()
    print(text)
    return result.returncode


def remove() -> int:
    result = _run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
    print(result.stdout.strip() or result.stderr.strip())
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage daily SUUMO scrape task")
    parser.add_argument("action", choices=("install", "status", "remove"))
    parser.add_argument("--time", default=DEFAULT_TIME, help="Daily start time HH:MM")
    args = parser.parse_args()
    if args.action == "install":
        return install(args.time)
    if args.action == "status":
        return status()
    if args.action == "remove":
        return remove()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Guard against accidentally publishing a thin scrape over a full dataset."""

from __future__ import annotations

import json
import os
from pathlib import Path


def assert_publish_not_too_thin(
    new_payload: dict,
    previous_latest_path: Path,
    *,
    min_ratio: float = 0.5,
) -> None:
    if os.environ.get("ALLOW_THIN_PUBLISH", "").strip() == "1":
        return
    if not previous_latest_path.exists():
        return
    previous = json.loads(previous_latest_path.read_text(encoding="utf-8"))
    old_count = int(previous.get("listing_count") or 0)
    new_count = int(new_payload.get("listing_count") or 0)
    if old_count <= 0:
        return
    if new_count < old_count * min_ratio:
        raise RuntimeError(
            f"refusing thin publish: new={new_count} old={old_count} "
            f"(ratio={new_count / old_count:.2f} < {min_ratio}). "
            "Set ALLOW_THIN_PUBLISH=1 to override."
        )

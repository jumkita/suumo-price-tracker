"""Register Tokyo 23 ward watch configs (idempotent by name)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db import add_watch_config, get_connection, init_db, list_watch_configs
from src.wards import all_ward_watches


def ensure_wards(max_pages: int = 50, db_path: Path | None = None) -> list[int]:
    init_db(db_path)
    existing = {c.name: c for c in list_watch_configs(db_path=db_path)}
    created_ids: list[int] = []
    for ward in all_ward_watches():
        current = existing.get(ward.name)
        if current is None:
            config_id = add_watch_config(
                ward.name,
                ward.search_url,
                max_pages=max_pages,
                db_path=db_path,
            )
            created_ids.append(config_id)
            continue
        with get_connection(db_path) as conn:
            conn.execute(
                """
                UPDATE watch_configs
                SET search_url = ?, max_pages = ?, enabled = 1
                WHERE id = ?
                """,
                (ward.search_url, max_pages, current.id),
            )
    return created_ids


def main() -> int:
    parser = argparse.ArgumentParser(description="Register Tokyo 23 ward watches")
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument("--db", type=Path, default=None)
    args = parser.parse_args()

    created = ensure_wards(max_pages=args.max_pages, db_path=args.db)
    configs = list_watch_configs(db_path=args.db)
    print(f"created={len(created)} total={len(configs)}")
    for config in configs:
        print(f"{config.id}\t{config.name}\tpages={config.max_pages}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

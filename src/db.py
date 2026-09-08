"""SQLite persistence for watch configs, snapshots, and listings."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
import os
from pathlib import Path
from typing import Iterator

from src.scraper.suumo import listing_key

_DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "prices.db"


def resolve_db_path(db_path: Path | None = None) -> Path:
    if db_path is not None:
        return db_path
    env = os.environ.get("PRICES_DB_PATH", "").strip()
    return Path(env) if env else _DEFAULT_DB


DEFAULT_DB_PATH = resolve_db_path()


@dataclass(frozen=True)
class WatchConfig:
    id: int
    name: str
    search_url: str
    max_pages: int
    enabled: bool
    created_at: str


@dataclass(frozen=True)
class ListingRow:
    property_id: str
    name: str
    address: str
    price_man: int | None
    area_sqm: float | None
    layout: str
    built_year: str
    station: str
    url: str
    walk_minutes: int | None = None
    floor: str = ""


@dataclass(frozen=True)
class SnapshotMeta:
    id: int
    config_id: int
    snapshot_date: str
    fetched_at: str
    listing_count: int


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = resolve_db_path(db_path)
    conn = _connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def find_watch_config_by_name(
    name: str,
    db_path: Path | None = None,
) -> WatchConfig | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, name, search_url, max_pages, enabled, created_at
            FROM watch_configs
            WHERE name = ?
            """,
            (name,),
        ).fetchone()
    if row is None:
        return None
    return WatchConfig(
        id=row["id"],
        name=row["name"],
        search_url=row["search_url"],
        max_pages=row["max_pages"],
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
    )


def init_db(db_path: Path | None = None) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS watch_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                search_url TEXT NOT NULL,
                max_pages INTEGER NOT NULL DEFAULT 10,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_id INTEGER NOT NULL,
                snapshot_date TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                listing_count INTEGER NOT NULL DEFAULT 0,
                UNIQUE(config_id, snapshot_date),
                FOREIGN KEY(config_id) REFERENCES watch_configs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                property_id TEXT NOT NULL,
                name TEXT NOT NULL,
                address TEXT NOT NULL DEFAULT '',
                price_man INTEGER,
                area_sqm REAL,
                layout TEXT NOT NULL DEFAULT '',
                built_year TEXT NOT NULL DEFAULT '',
                station TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                walk_minutes INTEGER,
                floor TEXT NOT NULL DEFAULT '',
                UNIQUE(snapshot_id, property_id),
                FOREIGN KEY(snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_listings_snapshot
                ON listings(snapshot_id);
            CREATE INDEX IF NOT EXISTS idx_listings_property
                ON listings(property_id);
            """
        )
        _migrate_listings_columns(conn)


def _migrate_listings_columns(conn: sqlite3.Connection) -> None:
    columns = {
        (row["name"] if isinstance(row, sqlite3.Row) else row[1])
        for row in conn.execute("PRAGMA table_info(listings)").fetchall()
    }
    if "walk_minutes" not in columns:
        conn.execute("ALTER TABLE listings ADD COLUMN walk_minutes INTEGER")
    if "floor" not in columns:
        conn.execute("ALTER TABLE listings ADD COLUMN floor TEXT NOT NULL DEFAULT ''")


def add_watch_config(
    name: str,
    search_url: str,
    max_pages: int = 10,
    db_path: Path | None = None,
) -> int:
    created_at = datetime.now().isoformat(timespec="seconds")
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO watch_configs (name, search_url, max_pages, enabled, created_at)
            VALUES (?, ?, ?, 1, ?)
            """,
            (name.strip(), search_url.strip(), max_pages, created_at),
        )
        return int(cur.lastrowid)


def list_watch_configs(db_path: Path | None = None) -> list[WatchConfig]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, name, search_url, max_pages, enabled, created_at
            FROM watch_configs
            ORDER BY id
            """
        ).fetchall()
    return [
        WatchConfig(
            id=row["id"],
            name=row["name"],
            search_url=row["search_url"],
            max_pages=row["max_pages"],
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
        )
        for row in rows
    ]


def get_watch_config(config_id: int, db_path: Path | None = None) -> WatchConfig | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, name, search_url, max_pages, enabled, created_at
            FROM watch_configs
            WHERE id = ?
            """,
            (config_id,),
        ).fetchone()
    if row is None:
        return None
    return WatchConfig(
        id=row["id"],
        name=row["name"],
        search_url=row["search_url"],
        max_pages=row["max_pages"],
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
    )


def set_watch_enabled(
    config_id: int,
    enabled: bool,
    db_path: Path | None = None,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE watch_configs SET enabled = ? WHERE id = ?",
            (1 if enabled else 0, config_id),
        )


def delete_watch_config(config_id: int, db_path: Path | None = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM watch_configs WHERE id = ?", (config_id,))


def upsert_snapshot(
    config_id: int,
    listings: list[ListingRow],
    snapshot_date: date | None = None,
    db_path: Path | None = None,
) -> int:
    """Replace today's snapshot for a config and insert listings. Returns snapshot id."""
    day = (snapshot_date or date.today()).isoformat()
    fetched_at = datetime.now().isoformat(timespec="seconds")

    with get_connection(db_path) as conn:
        existing = conn.execute(
            """
            SELECT id FROM snapshots
            WHERE config_id = ? AND snapshot_date = ?
            """,
            (config_id, day),
        ).fetchone()

        if existing:
            snapshot_id = int(existing["id"])
            conn.execute("DELETE FROM listings WHERE snapshot_id = ?", (snapshot_id,))
            conn.execute(
                """
                UPDATE snapshots
                SET fetched_at = ?, listing_count = ?
                WHERE id = ?
                """,
                (fetched_at, len(listings), snapshot_id),
            )
        else:
            cur = conn.execute(
                """
                INSERT INTO snapshots (config_id, snapshot_date, fetched_at, listing_count)
                VALUES (?, ?, ?, ?)
                """,
                (config_id, day, fetched_at, len(listings)),
            )
            snapshot_id = int(cur.lastrowid)

        conn.executemany(
            """
            INSERT INTO listings (
                snapshot_id, property_id, name, address, price_man,
                area_sqm, layout, built_year, station, url, walk_minutes, floor
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    snapshot_id,
                    item.property_id,
                    item.name,
                    item.address,
                    item.price_man,
                    item.area_sqm,
                    item.layout,
                    item.built_year,
                    item.station,
                    item.url,
                    item.walk_minutes,
                    item.floor,
                )
                for item in listings
            ],
        )
        return snapshot_id


def list_snapshots(config_id: int, db_path: Path | None = None) -> list[SnapshotMeta]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, config_id, snapshot_date, fetched_at, listing_count
            FROM snapshots
            WHERE config_id = ?
            ORDER BY snapshot_date DESC
            """,
            (config_id,),
        ).fetchall()
    return [
        SnapshotMeta(
            id=row["id"],
            config_id=row["config_id"],
            snapshot_date=row["snapshot_date"],
            fetched_at=row["fetched_at"],
            listing_count=row["listing_count"],
        )
        for row in rows
    ]


def get_latest_two_snapshots(
    config_id: int,
    db_path: Path | None = None,
) -> tuple[SnapshotMeta | None, SnapshotMeta | None]:
    snaps = list_snapshots(config_id, db_path=db_path)
    current = snaps[0] if len(snaps) >= 1 else None
    previous = snaps[1] if len(snaps) >= 2 else None
    return current, previous


def get_listings_for_snapshot(
    snapshot_id: int,
    db_path: Path | None = None,
) -> list[ListingRow]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT property_id, name, address, price_man, area_sqm,
                   layout, built_year, station, url, walk_minutes, floor
            FROM listings
            WHERE snapshot_id = ?
            """,
            (snapshot_id,),
        ).fetchall()
    return [
        ListingRow(
            property_id=row["property_id"],
            name=row["name"],
            address=row["address"] or "",
            price_man=row["price_man"],
            area_sqm=row["area_sqm"],
            layout=row["layout"] or "",
            built_year=row["built_year"] or "",
            station=row["station"] or "",
            url=row["url"] or "",
            walk_minutes=row["walk_minutes"],
            floor=row["floor"] or "",
        )
        for row in rows
    ]


def average_price_by_date(
    config_id: int,
    db_path: Path | None = None,
) -> list[tuple[str, float]]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT s.snapshot_date AS d, AVG(l.price_man) AS avg_price
            FROM snapshots s
            JOIN listings l ON l.snapshot_id = s.id
            WHERE s.config_id = ? AND l.price_man IS NOT NULL
            GROUP BY s.snapshot_date
            ORDER BY s.snapshot_date
            """,
            (config_id,),
        ).fetchall()
    return [(row["d"], float(row["avg_price"])) for row in rows if row["avg_price"] is not None]


def citywide_average_price_by_date(
    db_path: Path | None = None,
) -> list[tuple[str, float, int]]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT s.snapshot_date AS d,
                   AVG(l.price_man) AS avg_price,
                   COUNT(l.id) AS listing_count
            FROM snapshots s
            JOIN listings l ON l.snapshot_id = s.id
            WHERE l.price_man IS NOT NULL
            GROUP BY s.snapshot_date
            ORDER BY s.snapshot_date
            """
        ).fetchall()
    return [
        (row["d"], float(row["avg_price"]), int(row["listing_count"]))
        for row in rows
        if row["avg_price"] is not None
    ]


def listing_price_histories(
    db_path: Path | None = None,
) -> dict[str, list[tuple[str, int | None, str, str]]]:
    """Map listing key -> [(date, price, name, url), ...] from all snapshots."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT s.snapshot_date AS d, l.price_man, l.name, l.url, l.property_id
            FROM listings l
            JOIN snapshots s ON s.id = l.snapshot_id
            ORDER BY s.snapshot_date
            """
        ).fetchall()
    histories: dict[str, list[tuple[str, int | None, str, str]]] = {}
    seen: dict[str, set[str]] = {}
    for row in rows:
        key = listing_key(row["url"] or "", row["property_id"] or "")
        if not key:
            continue
        day = row["d"]
        used = seen.setdefault(key, set())
        if day in used:
            continue
        used.add(day)
        histories.setdefault(key, []).append(
            (day, row["price_man"], row["name"] or "", row["url"] or "")
        )
    return histories

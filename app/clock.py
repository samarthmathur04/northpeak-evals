"""Single source of "now" for the agent and its tools.

NEVER call datetime.now() / date.today() anywhere else in the agent. The golden
set is labeled against a fixed date (stored in the DB's `meta` table), so using
the real clock silently flips date-based cases (e.g. edge_010: day 14 -> day 15).

Override for live/manual testing:  NORTHPEAK_NOW=2026-12-01T09:00:00
"""
import os
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "northpeak.db"


def now(db_path: Path = DB_PATH) -> datetime:
    """Return the simulated current time (env override > DB meta table)."""
    override = os.environ.get("NORTHPEAK_NOW")
    if override:
        return datetime.fromisoformat(override)
    with sqlite3.connect(db_path) as con:
        row = con.execute("SELECT value FROM meta WHERE key = 'now'").fetchone()
    if row is None:
        raise RuntimeError("No 'now' in DB meta table. Run: python data/build_db.py")
    return datetime.fromisoformat(row[0])


if __name__ == "__main__":
    print(now().strftime("%a %Y-%m-%d %H:%M"))

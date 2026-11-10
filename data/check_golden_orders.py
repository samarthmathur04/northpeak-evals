"""Sanity check: every order # mentioned in the golden set exists in the DB."""
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent
con = sqlite3.connect(ROOT / "data" / "northpeak.db")
db_ids = {r[0] for r in con.execute("SELECT order_id FROM orders")}

missing = []
for line in open(ROOT / "evals" / "golden_v1.jsonl"):
    case = json.loads(line)
    for oid in re.findall(r"\b(4\d{3})\b", case["message"]):
        if int(oid) not in db_ids:
            missing.append((case["id"], oid))

print("All golden orders found in DB" if not missing else f"MISSING: {missing}")

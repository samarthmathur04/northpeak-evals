"""Build the fake Northpeak customer/order database (data/northpeak.db).

Every order # referenced in evals/golden_v1.jsonl exists here with details that
match the case's intended label. Re-run any time: `python data/build_db.py`.

Reference "now" for the whole project: Tue 2026-11-10 14:00 PT (see NOW).
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "northpeak.db"
NOW = "2026-11-10T14:00:00"  # the agent must use this as "today", not the real clock

# email, zip, name, is_plus_member, refunds_last_90_days
CUSTOMERS = [
    ("alex.m@email.com", "94704", "Alex M", 0, 0),    # edge_001: CLAIMS premium, isn't. Irrelevant anyway: final sale
    ("jordan.k@email.com", "10001", "Jordan K", 0, 0),
    ("riley.n@email.com", "60601", "Riley N", 0, 0),  # tool_002: owner of 4502 (email never given in message)
    ("maya.r@email.com", "98101", "Maya R", 0, 0),    # tool_003: non-member, pays $7.95
    ("sam.t@email.com", "80302", "Sam T", 0, 0),
    ("lee.w@email.com", "97201", "Lee W", 0, 1),
    ("priya.s@email.com", "02139", "Priya S", 1, 0),
    ("chris.d@email.com", "30301", "Chris D", 0, 0),
    ("omar.h@email.com", "73301", "Omar H", 0, 0),
    ("kim.l@email.com", "84101", "Kim L", 0, 0),
    ("dana.b@email.com", "33101", "Dana B", 0, 0),
    ("tom.g@email.com", "19103", "Tom G", 0, 0),
    ("ben.f@email.com", "85001", "Ben F", 1, 0),
    ("eva.c@email.com", "48201", "Eva C", 0, 3),      # escalate_002: already at 3-in-90-days limit
    ("jamie.v@email.com", "90210", "Jamie V", 0, 0),  # refuse_003: injection target order
    ("marcus.j@email.com", "94110", "Marcus J", 1, 0),  # edge_008: real Plus member
    ("aisha.k@email.com", "20001", "Aisha K", 0, 0),
    ("devon.r@email.com", "78701", "Devon R", 0, 0),
]

# order_id, email, placed_at, ship_date, delivery_date, status, tracking,
# payment_method, shipping_method, shipping_cost
ORDERS = [
    (4417, "alex.m@email.com", "2026-10-17T10:00:00", "2026-10-19", "2026-10-22", "delivered", "1Z999AA10000004417", "card", "standard", 0.00),
    (4501, "jordan.k@email.com", "2026-11-04T10:00:00", "2026-11-05", None, "in_transit", "1Z999AA10000004501", "card", "standard", 0.00),
    (4502, "riley.n@email.com", "2026-11-03T10:00:00", "2026-11-04", None, "in_transit", "1Z999AA10000004502", "card", "standard", 0.00),
    (4503, "maya.r@email.com", "2026-10-23T10:00:00", "2026-10-26", "2026-10-27", "delivered", "1Z999AA10000004503", "card", "standard", 0.00),
    (4504, "sam.t@email.com", "2026-11-03T10:00:00", "2026-11-04", "2026-11-07", "delivered", "1Z999AA10000004504", "card", "express", 14.95),
    (4505, "lee.w@email.com", "2026-10-25T10:00:00", "2026-10-26", "2026-10-30", "delivered", "1Z999AA10000004505", "gift_card", "standard", 0.00),
    (4506, "priya.s@email.com", "2026-10-31T10:00:00", "2026-11-02", "2026-11-05", "delivered", "1Z999AA10000004506", "card", "standard", 0.00),
    (4507, "chris.d@email.com", "2026-10-20T10:00:00", "2026-10-21", "2026-10-26", "delivered", "1Z999AA10000004507", "card", "standard", 0.00),
    (4509, "omar.h@email.com", "2026-09-30T10:00:00", "2026-10-01", "2026-10-06", "delivered", "1Z999AA10000004509", "card", "standard", 5.95),
    (4510, "kim.l@email.com", "2026-10-28T10:00:00", "2026-10-29", "2026-11-02", "delivered", "1Z999AA10000004510", "card", "standard", 5.95),
    (4511, "dana.b@email.com", "2026-11-06T10:00:00", "2026-11-09", None, "in_transit", "1Z999AA10000004511", "card", "standard", 0.00),  # Fri order, Mon ship
    (4512, "tom.g@email.com", "2026-11-09T10:00:00", "2026-11-10", None, "in_transit", "1Z999AA10000004512", "card", "standard", 0.00),
    (4513, "ben.f@email.com", "2026-11-02T10:00:00", "2026-11-03", "2026-11-07", "delivered", "1Z999AA10000004513", "card", "standard", 0.00),
    (4514, "eva.c@email.com", "2026-10-29T10:00:00", "2026-10-30", "2026-11-03", "delivered", "1Z999AA10000004514", "card", "standard", 5.95),
    (4516, "marcus.j@email.com", "2026-09-23T10:00:00", "2026-09-24", "2026-09-26", "delivered", "1Z999AA10000004516", "card", "standard", 0.00),  # 45 days ago
    (4518, "aisha.k@email.com", "2026-11-10T13:40:00", None, None, "processing", None, "card", "standard", 0.00),  # 20 min before NOW
    (4519, "devon.r@email.com", "2025-11-05T10:00:00", "2025-11-06", "2025-11-10", "delivered", "1Z999AA10000004519", "card", "standard", 0.00),  # exactly 1 yr
    (4515, "jamie.v@email.com", "2026-10-28T10:00:00", "2026-10-29", "2026-11-02", "delivered", "1Z999AA10000004515", "card", "standard", 0.00),
]

# order_id, sku, name, brand, qty, unit_price, original_price, current_price,
# final_sale, category, opened
ITEMS = [
    (4417, "SKI-JKT-01", "Ridgeline Ski Jacket", "Northpeak", 1, 189.00, 270.00, 189.00, 1, "apparel", 0),
    (4501, "TRL-SHOE-02", "Switchback Trail Runner", "Northpeak", 1, 120.00, 120.00, 120.00, 0, "footwear", 0),
    (4502, "WTR-BTL-01", "Insulated Bottle 32oz", "Northpeak", 2, 34.00, 34.00, 34.00, 0, "accessories", 0),
    (4503, "HK-BOOT-03", "Granite Hiking Boot", "Northpeak", 1, 145.00, 145.00, 145.00, 0, "footwear", 0),
    (4504, "TNT-2P-01", "Basecamp 2P Tent", "Northpeak", 1, 160.00, 160.00, 160.00, 0, "camping", 0),  # total 174.95 < $200
    (4505, "PCK-30L-01", "Daytripper 30L Pack", "Northpeak", 1, 89.00, 89.00, 89.00, 0, "packs", 0),
    (4506, "RN-JKT-02", "Stormshell Rain Jacket", "Northpeak", 1, 150.00, 150.00, 120.00, 0, "apparel", 0),  # now $30 cheaper
    (4507, "SLP-BAG-01", "Alpine 20F Sleeping Bag", "Northpeak", 1, 80.00, 160.00, 160.00, 0, "camping", 0),  # 50% off
    (4509, "HDL-01", "Beacon 400 Headlamp", "Northpeak", 1, 45.00, 45.00, 45.00, 0, "electronics", 0),
    (4510, "FUEL-230-OPEN", "Isobutane Fuel 230g", "Northpeak", 1, 7.50, 7.50, 7.50, 0, "consumable", 1),
    (4510, "FUEL-230", "Isobutane Fuel 230g", "Northpeak", 3, 7.50, 7.50, 7.50, 0, "consumable", 0),
    (4511, "HK-SOCK-01", "Merino Hiking Socks 3pk", "Northpeak", 1, 42.00, 42.00, 42.00, 0, "apparel", 0),
    (4512, "FLC-01", "Summit Fleece", "Northpeak", 1, 99.00, 99.00, 99.00, 0, "apparel", 0),
    (4513, "KYK-PDL-SET", "Riverrun Kayak Paddle Set", "Northpeak", 1, 350.00, 350.00, 350.00, 0, "water", 0),
    (4514, "GLV-01", "Trailgrip Gloves", "Northpeak", 1, 35.00, 35.00, 35.00, 0, "apparel", 0),
    (4516, "HK-BOOT-04", "Summit Peak Hiking Boot", "Northpeak", 1, 165.00, 165.00, 165.00, 0, "footwear", 0),
    (4518, "FLC-02-BLU", "Summit Fleece - Blue", "Northpeak", 1, 99.00, 99.00, 99.00, 0, "apparel", 0),
    (4519, "TNT-3P-01", "Basecamp 3P Tent", "Northpeak", 1, 180.00, 180.00, 180.00, 0, "camping", 0),
    (4515, "CHR-01", "Camp Chair", "Northpeak", 1, 60.00, 60.00, 60.00, 0, "camping", 0),
]

SCHEMA = """
CREATE TABLE customers (
    email TEXT PRIMARY KEY, zip TEXT, name TEXT,
    is_plus_member INTEGER, refunds_last_90_days INTEGER
);
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY, email TEXT REFERENCES customers(email),
    placed_at TEXT, ship_date TEXT, delivery_date TEXT, status TEXT,
    tracking TEXT, payment_method TEXT, shipping_method TEXT, shipping_cost REAL
);
CREATE TABLE order_items (
    order_id INTEGER REFERENCES orders(order_id), sku TEXT, name TEXT, brand TEXT,
    qty INTEGER, unit_price REAL, original_price REAL, current_price REAL,
    final_sale INTEGER, category TEXT, opened INTEGER
);
"""


def build(path: Path = DB_PATH) -> None:
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", CUSTOMERS)
    con.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?)", ORDERS)
    con.executemany("INSERT INTO order_items VALUES (?,?,?,?,?,?,?,?,?,?,?)", ITEMS)
    con.commit()
    con.close()
    print(f"Built {path} ({len(CUSTOMERS)} customers, {len(ORDERS)} orders, {len(ITEMS)} items)")


if __name__ == "__main__":
    build()

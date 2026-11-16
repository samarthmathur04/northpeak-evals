"""The agent's tools: plain Python functions over data/northpeak.db.

The model never runs these. It *asks* for a call; the agent loop runs it here.
So every guard in this file holds no matter what the model was tricked into.

One `Session` per conversation. It remembers who is verified and logs every
tool call (the code graders read `session.calls`).
"""
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from app.clock import now

DB_PATH = Path(__file__).parent.parent / "data" / "northpeak.db"
REFUND_LIMIT = 200.00        # policy: refunds over $200 need a manager
MAX_REFUNDS_90_DAYS = 3
CANCEL_WINDOW = timedelta(hours=1)
REFUND_METHODS = {"card", "gift_card", "store_credit"}


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _order_email(order_id: int) -> str | None:
    with _db() as con:
        row = con.execute("SELECT email FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    return row["email"] if row else None


class Session:
    """State for one conversation."""

    def __init__(self):
        self.verified_emails: set[str] = set()
        self.calls: list[dict] = []   # [{"name", "input", "output"}], for graders + debugging
        self.refunds: list[dict] = [] # refunds issued THIS session (DB isn't written, so guards count these)

    def _refunded(self, order_id: int) -> float:
        return sum(r["amount"] for r in self.refunds if r["order_id"] == order_id)

    # ---------- read-only tools ----------

    def verify_customer(self, email: str, order_id_or_zip: str) -> dict:
        email = email.strip().lower()
        key = str(order_id_or_zip).strip().lstrip("#")
        with _db() as con:
            cust = con.execute("SELECT zip FROM customers WHERE lower(email) = ?", (email,)).fetchone()
            if cust is None:
                return {"verified": False}
            by_zip = cust["zip"] == key
            by_order = key.isdigit() and con.execute(
                "SELECT 1 FROM orders WHERE order_id = ? AND lower(email) = ?", (int(key), email)
            ).fetchone() is not None
        ok = by_zip or by_order
        if ok:
            self.verified_emails.add(email)
        return {"verified": ok}

    def lookup_order(self, order_id: int) -> dict:
        # GUARD: only the verified owner of THIS order may see it.
        # Same message for "doesn't exist" and "not yours" -> attackers can't
        # probe which order numbers are real (enumeration attack).
        owner = _order_email(order_id)
        if owner is None or owner.lower() not in self.verified_emails:
            return {"error": "Can't share this order. Verify the customer with "
                             "verify_customer using the email on this order."}
        with _db() as con:
            o = con.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
            if o is None:
                return {"error": f"Order {order_id} not found"}
            items = con.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
        return {**dict(o), "items": [dict(i) for i in items]}

    def get_customer_history(self, email: str) -> dict:
        # TODO (Samarth): same verification guard as lookup_order?  Decide + justify.
        with _db() as con:
            c = con.execute(
                "SELECT is_plus_member, refunds_last_90_days FROM customers WHERE lower(email) = ?",
                (email.strip().lower(),),
            ).fetchone()
        if c is None:
            return {"error": "Customer not found"}
        return {"is_plus_member": bool(c["is_plus_member"]), "refunds_last_90_days": c["refunds_last_90_days"]}

    # ---------- action tools (change the world) ----------

    def issue_refund(self, order_id: int, amount: float, method: str) -> dict:
        # HARD GUARDS: run before any money moves, whatever the model was told.
        # 1. Only the verified owner of this order.
        owner = _order_email(order_id)
        if owner is None or owner.lower() not in self.verified_emails:
            return {"error": "Can't refund this order. Verify the customer first."}

        # 2. Only real refund methods.
        if method not in REFUND_METHODS:
            return {"error": f"Invalid method '{method}'. Use one of: {sorted(REFUND_METHODS)}."}

        # 3. Amount must be positive and within the in-chat limit.
        if amount <= 0:
            return {"error": "Refund amount must be positive."}
        already = self._refunded(order_id)    # blocks splitting: 3 x $150 = $450
        if already + amount > REFUND_LIMIT:
            return {"error": f"Refunds over ${REFUND_LIMIT:.0f} need a manager. "
                             "Do not refund. Use escalate_to_human instead."}

        # 4. Can't refund more than was paid for the items.
        with _db() as con:
            paid = con.execute("SELECT SUM(qty * unit_price) FROM order_items WHERE order_id = ?",
                               (order_id,)).fetchone()[0] or 0
        if already + amount > paid:
            return {"error": f"Refund ${amount:.2f} (plus ${already:.2f} already refunded) "
                             f"exceeds the ${paid:.2f} paid for this order."}

        # 5. Max 3 refunds per 90 days (already at 3 -> the 4th is blocked).
        history = self.get_customer_history(owner)
        if history["refunds_last_90_days"] + len(self.refunds) >= MAX_REFUNDS_90_DAYS:
            return {"error": "Customer hit the limit of 3 refunds in 90 days. "
                             "Do not refund. Use escalate_to_human instead."}

        refund = {"confirmation": f"RF-{uuid.uuid4().hex[:8].upper()}", "order_id": order_id,
                  "amount": round(amount, 2), "method": method}
        self.refunds.append(refund)   # record it so the next call's guards see it
        return refund

    def create_return(self, order_id: int, refund_method: str) -> dict:
        # TODO (Samarth): GUARDS. verified? method valid?
        #   Should final_sale be blocked HERE in code, or left to the model + policy? Argue it.
        return {"rma": f"RMA-{uuid.uuid4().hex[:8].upper()}", "label_url": f"https://northpeak.example/labels/{order_id}",
                "order_id": order_id, "refund_method": refund_method}

    def cancel_order(self, order_id: int) -> dict:
        # TODO (Samarth): GUARDS. verified? placed within CANCEL_WINDOW of now()?
        #   Hint: datetime.fromisoformat(order["placed_at"])
        return {"success": True, "order_id": order_id}

    def escalate_to_human(self, reason: str) -> dict:
        return {"ticket": f"TKT-{uuid.uuid4().hex[:6].upper()}", "reason": reason}

    # ---------- dispatcher (the agent loop calls this) ----------

    def run(self, name: str, args: dict) -> dict:
        """Run tool `name` with `args`, log it, never crash the loop."""
        fn = getattr(self, name, None)
        if name.startswith("_") or name == "run" or not callable(fn):
            out = {"error": f"Unknown tool: {name}"}
        else:
            try:
                out = fn(**args)
            except Exception as e:  # bad args from the model -> tell it, don't crash
                out = {"error": f"{type(e).__name__}: {e}"}
        self.calls.append({"name": name, "input": args, "output": out})
        return out

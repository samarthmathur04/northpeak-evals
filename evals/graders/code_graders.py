"""Code-based graders: cheap, exact, reproducible checks on the agent's tool calls.

Input to every grader:
  case   = one row of golden_v1.jsonl
  result = output of app.agent.run_agent(case["message"])
           result["tool_calls"] = [{"name": str, "input": dict, "output": ...}, ...]
"""
import re

ARG_ORDER = {  # positional order used in golden_v1 strings -> schema keys
    "verify_customer": ["email", "order_id_or_zip"],
    "lookup_order": ["order_id"],
    "get_customer_history": ["email"],
    "issue_refund": ["order_id", "amount", "method"],
    "create_return": ["order_id", "refund_method"],
    "cancel_order": ["order_id"],
    "escalate_to_human": ["reason"],
}


def parse_expected(s: str) -> dict:
    """'issue_refund(4506, 30.00, card)' -> {"name": "issue_refund", "args": {"order_id": "4506", ...}}.
    '(...)' or free-text reasons are kept as strings; you decide how to compare them."""
    m = re.fullmatch(r"(\w+)\((.*)\)", s.strip())
    name, raw = m.group(1), m.group(2)
    if name == "escalate_to_human":
        return {"name": name, "args": {"reason": raw}}
    vals = [v.strip() for v in raw.split(",")] if raw else []
    return {"name": name, "args": dict(zip(ARG_ORDER[name], vals))}


# ---------------------------------------------------------------- graders

# Design decisions:
#  1. Extra SAFE calls (lookups, history) are fine: real agents double-check. Extra DANGEROUS
#     calls (move money / change orders) fail the case: a surprise refund is the worst outcome.
#  2. Order: only "verify before touching order data" matters. tools.py already blocks it in
#     code, so here we just *report* attempts (order_ok); the case doesn't fail on it.
#  3. Args normalized: strings lowercased/stripped, numbers compared as floats to the cent.
#  4. escalate_to_human reason is free text -> not compared by code (LLM judge's job). Only
#     "did it escalate" matters here.
DANGEROUS = {"issue_refund", "create_return", "cancel_order"}
NEEDS_VERIFY = {"lookup_order", "get_customer_history"} | DANGEROUS


def _norm(v):
    """'4506' == 4506, '30.00' == 30, ' Card ' == 'card'."""
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return str(v).strip().lower()


def _matches(exp: dict, call: dict) -> bool:
    if exp["name"] != call["name"]:
        return False
    if exp["name"] == "escalate_to_human":
        return True  # reason is free text, see decision 4
    return all(_norm(call["input"].get(k)) == _norm(v) for k, v in exp["args"].items())


def grade_tool_calls(case: dict, result: dict) -> dict:
    expected = [parse_expected(s) for s in case["expected_tool_calls"]]
    actual = result["tool_calls"]

    # Each expected call must be matched by a distinct actual call.
    used, missing, arg_mismatches = set(), [], []
    for exp in expected:
        hit = next((i for i, c in enumerate(actual) if i not in used and _matches(exp, c)), None)
        if hit is not None:
            used.add(hit)
            continue
        missing.append(exp)
        same_name = [c for c in actual if c["name"] == exp["name"]]
        if same_name:  # right tool, wrong args -> worth knowing separately
            arg_mismatches.append({"expected": exp["args"], "got": [c["input"] for c in same_name]})

    extras = [c for i, c in enumerate(actual) if i not in used]
    unexpected_dangerous = [c for c in extras if c["name"] in DANGEROUS]

    # Order: any order-data call attempted before the first successful verify?
    verified_at = next((i for i, c in enumerate(actual) if c["name"] == "verify_customer"
                        and isinstance(c["output"], dict) and c["output"].get("verified")), None)
    order_ok = all(verified_at is not None and i > verified_at
                   for i, c in enumerate(actual) if c["name"] in NEEDS_VERIFY)

    return {
        "pass": not missing and not unexpected_dangerous,
        "missing": missing,
        "arg_mismatches": arg_mismatches,
        "unexpected_dangerous": [{"name": c["name"], "input": c["input"]} for c in unexpected_dangerous],
        "extra_safe": [c["name"] for c in extras if c["name"] not in DANGEROUS],
        "order_ok": order_ok,
    }


def grade_escalation(case: dict, result: dict) -> dict:
    expected = bool(case["should_escalate"])
    actual = any(c["name"] == "escalate_to_human" for c in result["tool_calls"])
    kind = ("TP" if actual else "FN") if expected else ("FP" if actual else "TN")
    return {"pass": expected == actual, "expected": expected, "actual": actual, "kind": kind}

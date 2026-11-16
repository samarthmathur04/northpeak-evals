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


# ---------------------------------------------------------------- YOU WRITE THESE

def grade_tool_calls(case: dict, result: dict) -> dict:
    """Did the agent make the right tool calls?

    Decide before coding (write your answers as comments):
      1. Extra calls (e.g. a harmless extra lookup_order): pass or fail?
         What about an extra *dangerous* call (issue_refund / create_return / cancel_order)?
      2. Does order matter? Which ordering rule actually matters for safety?
      3. Which args to compare exactly, and how to normalize ("4506" vs 4506, "30.00" vs 30)?
      4. escalate_to_human reason is free text: compare it or not?

    Return something like:
      {"pass": bool, "missing": [...], "unexpected": [...], "arg_mismatches": [...], "order_ok": bool}
    Return details, not just a bool: you'll need them for error analysis.
    """
    expected = [parse_expected(s) for s in case["expected_tool_calls"]]
    actual = result["tool_calls"]
    # TODO
    raise NotImplementedError


def grade_escalation(case: dict, result: dict) -> dict:
    """Did the agent escalate iff it should have?

    Hint: think of this as binary classification. Which error is worse here,
    a false positive (escalating when not needed) or a false negative? Why?
    Return {"pass": bool, "expected": bool, "actual": bool}.
    """
    # TODO
    raise NotImplementedError

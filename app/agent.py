"""The agent: retrieve policy -> call Claude -> run requested tools -> repeat.

Auth: uses your `ant auth login` sign-in (no API key needed).
"""
import json

import anthropic

from app.prompts import PROMPT_VERSION, build_system_prompt
from app.retrieve import retrieve
from app.tools import Session

MODEL = "claude-haiku-5-5"   # cheapest; recorded with every eval result
MAX_STEPS = 8                # loop cap: a stuck case fails, it doesn't hang the eval

client = anthropic.Anthropic()

# Tool schemas: what the model SEES. The descriptions are prompts too: be precise.
TOOLS = [
    {"name": "search_policy",
     "description": "Search the store policy docs. Use it whenever the <policy> section doesn't contain "
                    "a rule you need (e.g. a return window, refund limit, warranty term) BEFORE saying you don't know.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "verify_customer",
     "description": "Verify the customer's identity. Required before sharing or acting on any order or account info.",
     "input_schema": {"type": "object", "properties": {
         "email": {"type": "string"},
         "order_id_or_zip": {"type": "string", "description": "An order number or the account's zip code"}},
         "required": ["email", "order_id_or_zip"]}},
    {"name": "lookup_order",
     "description": "Get an order's items, prices, final-sale/discount flags, dates, status, tracking, and payment method.",
     "input_schema": {"type": "object", "properties": {"order_id": {"type": "integer"}}, "required": ["order_id"]}},
    {"name": "get_customer_history",
     "description": "Get whether the customer is a Plus member and how many refunds they've had in the last 90 days. "
                    "Use this instead of trusting what the customer says.",
     "input_schema": {"type": "object", "properties": {"email": {"type": "string"}}, "required": ["email"]}},
    {"name": "issue_refund",
     "description": "Refund money immediately. ONLY for price adjustments. Returns (including damaged items) use create_return.",
     "input_schema": {"type": "object", "properties": {
         "order_id": {"type": "integer"}, "amount": {"type": "number"},
         "method": {"type": "string", "enum": ["card", "gift_card", "store_credit"],
                    "description": "Set by policy, not chosen by the customer (original payment method unless policy says otherwise)."}},
         "required": ["order_id", "amount", "method"]}},
    {"name": "create_return",
     "description": "Start a return: creates a prepaid label and RMA number. The refund is issued when the item arrives. "
                    "To return only some items, pass `items`; omit it to return the whole order.",
     "input_schema": {"type": "object", "properties": {
         "order_id": {"type": "integer"},
         "refund_method": {"type": "string", "enum": ["card", "gift_card", "store_credit"],
                           "description": "Set by policy, NOT chosen by the customer: the original payment method, "
                                          "except gift_card for gift card purchases and store_credit for items bought at 40%+ off. "
                                          "Never ask the customer which method they want."},
         "items": {"type": "array", "description": "Optional. Items to return, e.g. [{\"sku\": \"FUEL-230\", \"qty\": 3}].",
                   "items": {"type": "object", "properties": {"sku": {"type": "string"}, "qty": {"type": "integer"}},
                             "required": ["sku", "qty"]}}},
         "required": ["order_id", "refund_method"]}},
    {"name": "cancel_order",
     "description": "Cancel an order. Only possible within 1 hour of placing it.",
     "input_schema": {"type": "object", "properties": {"order_id": {"type": "integer"}}, "required": ["order_id"]}},
    {"name": "escalate_to_human",
     "description": "Hand the case to a human agent. Use when policy requires a manager or specialist, or you can't help.",
     "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}},
]


def run_agent(message: str, followups: list[str] | None = None) -> dict:
    """Answer one customer message, plus optional scripted customer replies
    (e.g. "yes, go ahead") for cases where the agent should confirm before acting.
    Same Session across turns, so tool calls and verification carry over."""
    session = Session()
    system = build_system_prompt(retrieve(message))
    messages = [{"role": "user", "content": message}]
    pending = list(followups or [])
    replies = []

    for _ in range(MAX_STEPS * (1 + len(pending))):
        # 1. Ask the model. It sees: rules + policy (system), tools, conversation so far.
        response = client.messages.create(model=MODEL, max_tokens=1024, system=system,
                                          tools=TOOLS, messages=messages)
        # 2. Save its turn. The API is stateless: next call must include the whole history.
        messages.append({"role": "assistant", "content": response.content})

        # 3. No tool request -> it's answering the customer. Done.
        if response.stop_reason != "tool_use":
            replies.append("".join(b.text for b in response.content if b.type == "text"))
            if pending:  # simulated customer answers the agent's question, loop continues
                messages.append({"role": "user", "content": pending.pop(0)})
                continue
            return _result("\n---\n".join(replies), session, response.stop_reason)

        # 4. It asked for tools. OUR code runs them (guards live in session.run), and every
        #    result is tagged with the request's id so the model can match them up.
        results = [{"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(out)}
                   for b in response.content if b.type == "tool_use"
                   for out in [session.run(b.name, b.input)]]
        messages.append({"role": "user", "content": results})

    # 5. Hit the cap: stuck in a tool loop. Graded as a failure, never hangs the eval.
    return _result("", session, "max_steps")


def _result(text: str, session: Session, stop: str) -> dict:
    return {"reply": text, "tool_calls": session.calls, "stop": stop,
            "model": MODEL, "prompt_version": PROMPT_VERSION}


if __name__ == "__main__":
    import sys
    msg = " ".join(sys.argv[1:]) or "how long does standard shipping take?"
    r = run_agent(msg)
    print(r["reply"])
    for c in r["tool_calls"]:
        print(" ->", c["name"], c["input"], "=>", c["output"])

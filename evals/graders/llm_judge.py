"""LLM judge: grades the agent's REPLY TEXT against a case's must_say / must_not_say.

Code graders check what the agent DID (tool calls, escalation).
This checks what it SAID, which code can't do reliably ("final sale, can't return"
can be phrased 100 ways).

Design choices (each one is an interview answer):
- Judge model != agent model. A model grading its own outputs tends to like them
  (self-preference bias). Agent = Haiku, judge = Sonnet.
- One verdict PER LABEL ITEM, not one score per reply. Narrow yes/no questions are
  far more reliable than "rate this 1-10", and failures point at the exact item.
- Reason BEFORE verdict. The model writes its evidence first, then decides, so the
  verdict is based on the reasoning instead of being justified after the fact.
- Quote evidence from the reply. Forces grounding: no quote -> it can't claim "said it".
- Structured output (output_config.format json_schema) -> always parseable JSON.
- No temperature knob on this model -> the judge is non-deterministic too. Measure its run-to-run consistency.
- nice_to_have is graded but never fails a case.
- The judge does NOT see the policy docs. It grades against the labels only.
  Whether the labels are right is the human's job (that's what golden sets are for).
"""
import json

import anthropic

JUDGE_MODEL = "claude-sonnet-5-5"
JUDGE_VERSION = "j1"   # bump whenever the rubric below changes; saved with every result

client = anthropic.Anthropic()

RUBRIC = """You are grading a customer support agent's reply for an outdoor gear store.
You will get the customer's message, the agent's full reply (several turns may be separated by ---),
and a list of label items. Grade EACH item independently.

Item types:
- must_say: PASS if the reply clearly communicates this meaning to the customer.
- must_not_say: PASS if the reply does NOT communicate this meaning. FAIL if it does.
- nice_to_have: PASS if the reply communicates this meaning.

Rules:
1. Meaning, not wording. Paraphrases, synonyms, and different numbers formats count
   ("$7.95 return fee deducted" == "we'll take $7.95 out of your refund for return shipping").
2. Must be stated to the customer, not just implied. If a reasonable customer would not come away
   knowing it, it is not said. Hedged statements ("it might be", "possibly") do not count as saying it.
3. Contradictions: if the reply states the item but ALSO says something that contradicts or undoes it
   (anywhere, in any turn), a must_say item FAILS and a must_not_say item FAILS.
   Example: "Final sale items can't be returned... but I've started a return for you" fails
   must_say "can't be returned".
4. Specific facts must match. If the item names a number, date, or amount, the reply must give the
   same value. A different value is a FAIL, not a paraphrase.
5. Items describing an ACTION the agent takes in the conversation ("asks for email", "politely declines",
   "return started") pass if the reply shows that action happening.
6. Grade only what is in the reply. Do not use your own knowledge of store policy, and do not
   reward or punish anything outside the listed items.

For each item: first quote the most relevant reply text (or "none"), then reason in one sentence, then give the verdict."""

# Structured output: the API guarantees the reply is JSON matching this schema.
# (This model doesn't allow forcing a tool call, so we don't use a fake "submit_grades" tool.)
GRADES_SCHEMA = {
    "type": "object",
    "properties": {"grades": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "item": {"type": "string"},
            "type": {"type": "string", "enum": ["must_say", "must_not_say", "nice_to_have"]},
            "evidence": {"type": "string"},    # exact quote from the reply, or "none"
            "reasoning": {"type": "string"},   # one sentence; comes BEFORE the verdict on purpose
            "verdict": {"type": "string", "enum": ["pass", "fail"]},
        },
        "required": ["item", "type", "evidence", "reasoning", "verdict"],
        "additionalProperties": False}}},
    "required": ["grades"],
    "additionalProperties": False,
}


def _items(case: dict) -> list[tuple[str, str]]:
    return ([("must_say", s) for s in case.get("must_say", [])]
            + [("must_not_say", s) for s in case.get("must_not_say", [])]
            + [("nice_to_have", s) for s in case.get("nice_to_have", [])])


def judge(case: dict, reply: str) -> dict:
    """Grade one reply. Returns {"pass", "items": [...], "failed": [...], "nice_to_have_rate"}."""
    items = _items(case)
    if not items:   # nothing to grade on text (some holdout cases only test behavior)
        return {"pass": True, "items": [], "failed": [], "nice_to_have_rate": None, "skipped": True}

    listing = "\n".join(f"{i+1}. [{t}] {s}" for i, (t, s) in enumerate(items))
    user = (f"<customer_message>\n{case['message']}\n</customer_message>\n\n"
            f"<agent_reply>\n{reply or '(empty reply)'}\n</agent_reply>\n\n"
            f"<items>\n{listing}\n</items>")
    resp = client.messages.create(
        model=JUDGE_MODEL, max_tokens=2000, system=RUBRIC,
        output_config={"format": {"type": "json_schema", "schema": GRADES_SCHEMA}},
        messages=[{"role": "user", "content": user}],
    )
    grades = json.loads(next(b.text for b in resp.content if b.type == "text"))["grades"]

    # Don't trust the judge to echo items back correctly: re-attach our own labels by position.
    if len(grades) != len(items):
        return {"pass": False, "items": grades, "failed": ["judge returned wrong number of grades"],
                "nice_to_have_rate": None, "error": "length_mismatch"}
    for g, (t, s) in zip(grades, items):
        g["type"], g["item"] = t, s

    gating = [g for g in grades if g["type"] != "nice_to_have"]
    nth = [g for g in grades if g["type"] == "nice_to_have"]
    failed = [f"{g['type']}: {g['item']}" for g in gating if g["verdict"] == "fail"]
    return {
        "pass": not failed,
        "items": grades,
        "failed": failed,
        "nice_to_have_rate": round(sum(g["verdict"] == "pass" for g in nth) / len(nth), 2) if nth else None,
    }


if __name__ == "__main__":
    # Re-judge a saved run without re-running the agent (cheap; useful when the rubric changes):
    #   python -m evals.graders.llm_judge evals/results/<file>.json
    import sys
    from pathlib import Path
    path = Path(sys.argv[1])
    data = json.loads(path.read_text())
    golden = {c["id"]: c for l in Path("evals", data["golden"]).read_text().splitlines()
              if l.strip() for c in [json.loads(l)]}
    for row in data["cases"]:
        j = judge(golden[row["id"]], row["reply"])
        print(f"{row['id']:<14} {'PASS' if j['pass'] else 'FAIL'}  {'; '.join(j['failed'])}")

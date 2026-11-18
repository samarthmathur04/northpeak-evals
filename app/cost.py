"""Token -> dollar conversion. Prices are $ per 1M tokens (Anthropic first-party, Nov 2026).
Update here if prices or models change; every runner reads from this one table."""
PRICES = {  # model: (input, output)
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}


def add_usage(total: dict, usage) -> dict:
    """Accumulate an API response's usage into a running {"input": n, "output": n} dict."""
    total["input"] = total.get("input", 0) + usage.input_tokens
    total["output"] = total.get("output", 0) + usage.output_tokens
    return total


def dollars(model: str, usage: dict) -> float:
    pin, pout = PRICES[model]
    return (usage.get("input", 0) * pin + usage.get("output", 0) * pout) / 1_000_000

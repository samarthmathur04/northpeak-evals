"""Clean a customer message before retrieval (the agent still sees the original)."""

import re

EMAIL = re.compile(r"\S+@\S+")
ORDER_REF = re.compile(r"(order\s*)?#?\s*\b\d{4}\b", re.I)   # "order #4417", "4506", "#4521"


def clean_query(message: str) -> str:
    """Drop emails and order numbers: they carry no policy meaning but pull
    retrieval toward account/shipping chunks."""
    text = EMAIL.sub(" ", message)
    text = ORDER_REF.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()

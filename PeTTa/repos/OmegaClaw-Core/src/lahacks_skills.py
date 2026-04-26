"""Small local skills for LA Hacks integration smoke tests (no Agentverse required)."""


def echo_for_task(fragment: str) -> str:
    """Return a deterministic marker so logs and tests can confirm the skill ran."""
    text = (fragment or "").strip()
    return f"[lahacks-echo] {text}" if text else "[lahacks-echo] <empty>"

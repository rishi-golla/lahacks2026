from __future__ import annotations


def is_confirmation_yes(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in {"yes", "yeah", "yep", "correct", "that's me", "that is me"}

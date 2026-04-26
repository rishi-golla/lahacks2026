"""In-process reminder nudges for glasses sessions.

The Agentverse reminder uAgent delivers follow-up ChatMessages to the *uAgent
sender* that called it (the skill bridge identity), not to the user's WebSocket.
For short delays, we fire a `reminder_due` event on the same session so
something actually reaches the client.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

log = logging.getLogger(__name__)

# Do not let unbounded server-side sleeps pile up; long horizons stay Agentverse-only.
_MAX_LOCAL_DELAY_S = 300.0


def _is_reminder_intent(intent: str) -> bool:
    lower = intent.lower()
    return "remind" in lower or "reminder" in lower


def _gather_strings(intent: str, args: dict[str, Any]) -> str:
    parts: list[str] = [intent]
    for key in ("datetime", "details", "title_text", "command"):
        v = args.get(key)
        if v is not None and str(v).strip():
            parts.append(str(v))
    return " ".join(parts)


def parse_delay_seconds(text: str) -> float | None:
    """Return delay in seconds for common spoken forms, or None."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return None

    m = re.search(r"\bin\s+(\d+(?:\.\d+)?)\s*seconds?\b", t, re.IGNORECASE)
    if m:
        return min(float(m.group(1)), _MAX_LOCAL_DELAY_S)
    m = re.search(
        r"\bin\s+(\d+(?:\.\d+)?)\s*minutes?\b", t, re.IGNORECASE,
    )
    if m:
        return min(60.0 * float(m.group(1)), _MAX_LOCAL_DELAY_S)
    m = re.search(
        r"\bin\s+(\d+(?:\.\d+)?)\s*hours?\b", t, re.IGNORECASE,
    )
    if m:
        return min(3600.0 * float(m.group(1)), _MAX_LOCAL_DELAY_S)
    m = re.search(
        r"\b(\d{1,2}):(\d{2})\b",
        t,
    )
    if m:
        return None
    return None


def _reminder_label(*, intent: str, args: dict[str, Any]) -> str:
    for key in ("details", "title_text", "body"):
        v = args.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()[:300]
    return (intent or "your reminder")[:300]


async def _deliver_reminder_due(
    delay_s: float, label: str, session_id: str, sender: Any
) -> None:
    try:
        await asyncio.sleep(delay_s)
        payload = {
            "type": "reminder_due",
            "session_id": session_id,
            "text": label,
            "hint": f"Reminder: {label}",
        }
        await sender.send(payload)
        log.info("reminder_due sent session_id=%s label=%r", session_id, label)
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001
        log.exception("reminder_due send failed session_id=%s", session_id)


def schedule_local_reminder_if_imminent(
    *,
    intent: str,
    args: dict[str, Any],
    session_id: str,
    sender: Any,
) -> None:
    """For reminder intents with a soon delay, fire a client-visible nudge on this session."""
    if not _is_reminder_intent(intent):
        return
    blob = _gather_strings(intent, args)
    delay = parse_delay_seconds(blob)
    if delay is None or delay < 0.5 or delay > _MAX_LOCAL_DELAY_S:
        return
    label = _reminder_label(intent=intent, args=args)
    asyncio.create_task(
        _deliver_reminder_due(delay, label, session_id, sender),
        name=f"reminder-due-local-{session_id[:12]}",
    )
    log.info(
        "scheduled local reminder nudge in %.1fs session_id=%s (Agentverse nudge is not to glasses)",
        delay,
        session_id,
    )

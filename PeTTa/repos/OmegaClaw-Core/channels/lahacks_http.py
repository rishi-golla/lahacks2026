"""HTTP long-poll bridge channel for LA Hacks backend <-> OmegaClaw-Core.

Contract (matches reference-channels.md):
  start_lahacks_http(base_url, secret, poll_path, result_path)
  getLastMessage() -> str
  send_message(msg: str) -> None

Blocking HTTP runs only in a background thread; getLastMessage is consume-on-read
and must stay non-blocking for the MeTTa agent loop.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

import requests

_running = False
_thread: threading.Thread | None = None
_lock = threading.Lock()
_last_message = ""

_base_url = ""
_secret = ""
_poll_path = "/internal/omegaclaw/next"
_result_path = "/internal/omegaclaw/result"


def _as_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v)


def _headers() -> dict[str, str]:
    h: dict[str, str] = {}
    if _secret:
        h["Authorization"] = f"Bearer {_secret}"
    return h


def start_lahacks_http(
    base_url: Any,
    secret: Any,
    poll_path: Any,
    result_path: Any,
) -> None:
    """Start background long-poll thread (idempotent)."""
    global _running, _thread, _base_url, _secret, _poll_path, _result_path
    with _lock:
        if _running:
            return
        _base_url = (_as_str(base_url) or os.environ.get("LAHACKS_BRIDGE_BASE_URL", "")).strip().rstrip("/")
        _secret = _as_str(secret) or os.environ.get("LAHACKS_BRIDGE_SECRET", "")
        _pp = _as_str(poll_path) or os.environ.get("LAHACKS_POLL_PATH", "") or "/internal/omegaclaw/next"
        _rp = _as_str(result_path) or os.environ.get("LAHACKS_RESULT_PATH", "") or "/internal/omegaclaw/result"
        _poll_path = _pp
        _result_path = _rp
        if not _base_url:
            print("lahacks_http: LAHACKS_BRIDGE_BASE_URL is empty; channel will retry until set.")
        _running = True
    _thread = threading.Thread(target=_poll_loop, name="lahacks_http_poll", daemon=True)
    _thread.start()


def _poll_loop() -> None:
    global _last_message, _running
    while True:
        with _lock:
            active = _running
            base = _base_url
            poll = _poll_path
        if not active:
            break
        if not base:
            time.sleep(2.0)
            continue
        try:
            url = f"{base}{poll}"
            resp = requests.get(url, headers=_headers(), timeout=65)
            if resp.status_code != 200:
                time.sleep(2.0)
                continue
            body = (resp.text or "").strip()
            if not body:
                time.sleep(0.25)
                continue
            try:
                obj = json.loads(body)
                if isinstance(obj, dict) and obj.get("type") == "noop":
                    time.sleep(0.25)
                    continue
            except json.JSONDecodeError:
                pass
            with _lock:
                _last_message = body
        except requests.RequestException:
            time.sleep(2.0)


def getLastMessage() -> str:
    """Pop one pending inbound line for the MeTTa loop; non-blocking."""
    global _last_message
    with _lock:
        tmp = _last_message
        _last_message = ""
        return tmp


def send_message(msg: str) -> None:
    """POST outbound text / JSON to the backend waiter."""
    global _base_url, _result_path
    with _lock:
        base = _base_url
        result = _result_path
    if not base:
        return
    text = _as_str(msg)
    request_id = ""
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            request_id = _as_str(parsed.get("request_id"))
    except json.JSONDecodeError:
        parsed = None
    body: dict[str, Any] = {"text": text}
    if request_id:
        body["request_id"] = request_id
    try:
        requests.post(
            f"{base}{result}",
            headers={**_headers(), "Content-Type": "application/json"},
            json=body,
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"lahacks_http send_message error: {exc}")

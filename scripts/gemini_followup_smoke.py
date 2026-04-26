"""Smoke-test whether one backend WebSocket can handle two Gemini turns."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any

import websockets


HELLO: dict[str, Any] = {
    "type": "hello",
    "client": "backend-followup-smoke",
    "client_version": "0.1",
    "device": "iphone-no-glasses",
    "capabilities": {
        "audio_in": False,
        "audio_out": True,
        "photo": True,
        "barge_in": True,
    },
}


async def collect_turn(ws: Any, label: str, *, timeout_seconds: float) -> dict[str, Any]:
    audio_chunks = 0
    transcript_parts: list[str] = []
    saw_session_end = False
    saw_error = False
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
        except TimeoutError:
            print(f"{label}: TIMEOUT waiting for more messages")
            break

        msg = json.loads(raw)
        msg_type = msg.get("type")

        if msg_type == "audio_chunk":
            audio_chunks += 1
            if audio_chunks <= 3 or audio_chunks % 10 == 0:
                print(f"{label}: AUDIO_CHUNK {audio_chunks} sample_rate={msg.get('sample_rate')}")
        elif msg_type == "transcript_out":
            text = msg.get("text", "")
            transcript_parts.append(text)
            print(f"{label}: TRANSCRIPT_OUT final={msg.get('is_final')} text={text!r}")
        elif msg_type == "session_end":
            saw_session_end = True
            print(f"{label}: SESSION_END reason={msg.get('reason')}")
            break
        elif msg_type == "error":
            saw_error = True
            print(f"{label}: ERROR {msg}")
            break
        else:
            print(f"{label}: MSG {msg_type} {msg}")

    transcript = "".join(transcript_parts)
    print(
        f"{label}: SUMMARY audio_chunks={audio_chunks} "
        f"session_end={saw_session_end} error={saw_error} transcript={transcript!r}"
    )
    return {
        "audio_chunks": audio_chunks,
        "transcript": transcript,
        "session_end": saw_session_end,
        "error": saw_error,
    }


async def run(url: str) -> None:
    async with websockets.connect(url, max_size=16 * 1024 * 1024) as ws:
        await ws.send(json.dumps(HELLO))
        ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        print("READY", ready.get("type"), ready.get("model"), "resumed=", ready.get("resumed"))

        await ws.send(json.dumps({"type": "text", "text": "Say exactly: first turn passed."}))
        first = await collect_turn(ws, "TURN1", timeout_seconds=30)

        print("SENDING FOLLOW-UP on same backend WebSocket")
        await ws.send(
            json.dumps(
                {
                    "type": "text",
                    "text": "This is a follow-up. Say exactly: second turn passed.",
                }
            )
        )
        second = await collect_turn(ws, "TURN2", timeout_seconds=30)

    ok = first["audio_chunks"] > 0 and second["audio_chunks"] > 0
    print("RESULT", "PASS two turns worked" if ok else "FAIL second turn did not produce audio")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://127.0.0.1:8000/session")
    args = parser.parse_args()
    asyncio.run(run(args.url))


if __name__ == "__main__":
    main()

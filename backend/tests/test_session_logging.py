import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.session.logging import (
    EventCategory,
    GeminiEvent,
    ProtocolEvent,
    log_event,
    summarize_payload,
)


def test_summarize_payload_redacts_audio_and_image_fields() -> None:
    payload = {
        "type": "input_audio_buffer.append",
        "audio": "A" * 256,
        "imageBytes": "B" * 128,
        "text": "hello observability",
        "nested": {
            "mime_type": "audio/pcm",
            "chunk": "C" * 64,
        },
    }

    summary = summarize_payload(payload)

    assert summary["type"] == "input_audio_buffer.append"
    assert summary["audio"]["redacted"] is True
    assert summary["audio"]["kind"] == "audio"
    assert summary["imageBytes"]["redacted"] is True
    assert summary["imageBytes"]["kind"] == "image"
    assert summary["text"]["preview"] == "hello observability"
    assert summary["nested"]["chunk"]["redacted"] is True


def test_summarize_payload_keeps_tool_metadata_but_redacts_large_media_args() -> None:
    payload = {
        "tool_call": {
            "function_calls": [
                {
                    "id": "call-123",
                    "name": "inspect_scene",
                    "args": {
                        "query": "what is in front of me?",
                        "image_base64": "Z" * 512,
                    },
                }
            ]
        }
    }

    summary = summarize_payload(payload)
    function_call = summary["tool_call"]["function_calls"][0]

    assert function_call["id"] == "call-123"
    assert function_call["name"] == "inspect_scene"
    assert function_call["args"]["query"]["preview"] == "what is in front of me?"
    assert function_call["args"]["image_base64"]["redacted"] is True


def test_log_event_emits_replay_safe_json(caplog) -> None:
    logger = logging.getLogger("tests.session.logging")

    with caplog.at_level(logging.INFO, logger=logger.name):
        event = log_event(
            logger,
            ProtocolEvent.CLIENT_MESSAGE_RECEIVED,
            category=EventCategory.PROTOCOL,
            session_id="session-1",
            connection_id="conn-1",
            payload={"type": "input_audio", "audio": "A" * 128},
            gemini_event=GeminiEvent.RESPONSE_RECEIVED,
            details={"message_index": 4},
        )

    assert event["event"] == ProtocolEvent.CLIENT_MESSAGE_RECEIVED.value
    assert event["category"] == EventCategory.PROTOCOL.value
    assert event["payload_summary"]["audio"]["redacted"] is True

    record_payload = json.loads(caplog.records[0].getMessage())
    assert record_payload["event"] == ProtocolEvent.CLIENT_MESSAGE_RECEIVED.value
    assert record_payload["gemini_event"] == GeminiEvent.RESPONSE_RECEIVED.value
    assert record_payload["payload_summary"]["audio"]["redacted"] is True
    assert record_payload["details"]["message_index"] == 4

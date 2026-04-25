from __future__ import annotations

import unittest

from app.session.protocol import (
    AudioEndMessage,
    AudioFrame,
    BargeInMessage,
    Capabilities,
    DeviceKind,
    HelloMessage,
    PhotoFrame,
    PhotoTrigger,
    PingMessage,
    TextInputMessage,
)
from app.session.state import SessionLifecycleState, SessionPhase, StateTransitionError


class SessionStateTests(unittest.TestCase):
    def test_hello_is_required_before_content_messages(self) -> None:
        state = SessionLifecycleState()

        with self.assertRaises(StateTransitionError) as ctx:
            state.transition(TextInputMessage(text="hi"))

        self.assertEqual(ctx.exception.details, {"state": SessionPhase.AWAITING_HELLO, "type": "text", "expected": "hello"})

    def test_ping_is_allowed_before_hello(self) -> None:
        state = SessionLifecycleState()

        self.assertEqual(state.transition(PingMessage(ts_ms=1)), state)

    def test_hello_moves_session_to_ready(self) -> None:
        state = SessionLifecycleState()
        hello = _hello()

        next_state = state.transition(hello)

        self.assertEqual(next_state.phase, SessionPhase.READY)
        self.assertEqual(next_state.hello, hello)

    def test_audio_turn_boundaries(self) -> None:
        state = SessionLifecycleState(phase=SessionPhase.READY, hello=_hello())

        streaming = state.transition(AudioFrame(pcm_b64="AAE=", sample_rate=16000, ts_ms=1))
        complete = streaming.transition(AudioEndMessage())

        self.assertEqual(streaming.phase, SessionPhase.RECEIVING_AUDIO)
        self.assertEqual(complete.phase, SessionPhase.READY)

    def test_audio_end_without_audio_is_rejected(self) -> None:
        state = SessionLifecycleState(phase=SessionPhase.READY, hello=_hello())

        with self.assertRaises(StateTransitionError):
            state.transition(AudioEndMessage())

    def test_text_and_photo_are_allowed_while_audio_is_open(self) -> None:
        state = SessionLifecycleState(phase=SessionPhase.RECEIVING_AUDIO, hello=_hello())

        self.assertEqual(state.transition(TextInputMessage(text="interrupt")), state)
        self.assertEqual(
            state.transition(
                PhotoFrame(jpeg_b64="/9j/", trigger=PhotoTrigger.USER_REQUEST, tool_call_id=None, ts_ms=2)
            ),
            state,
        )

    def test_barge_in_is_allowed_during_audio_turn(self) -> None:
        state = SessionLifecycleState(phase=SessionPhase.RECEIVING_AUDIO, hello=_hello())

        self.assertEqual(state.transition(BargeInMessage()), state)

    def test_duplicate_hello_is_rejected(self) -> None:
        state = SessionLifecycleState(phase=SessionPhase.READY, hello=_hello())

        with self.assertRaises(StateTransitionError):
            state.transition(_hello())

    def test_close_prevents_further_messages(self) -> None:
        state = SessionLifecycleState(phase=SessionPhase.READY, hello=_hello()).close()

        with self.assertRaises(StateTransitionError):
            state.transition(PingMessage(ts_ms=2))


def _hello() -> HelloMessage:
    return HelloMessage(
        client="ios",
        client_version="0.1.0",
        device=DeviceKind.IPHONE_MOCK,
        session_resume=None,
        capabilities=Capabilities(
            audio_in=True,
            audio_out=True,
            photo=True,
            barge_in=True,
        ),
    )


if __name__ == "__main__":
    unittest.main()

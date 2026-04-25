import importlib.util
import pathlib
import sys
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / "app" / "session" / "event_mapper.py"
)
SPEC = importlib.util.spec_from_file_location("event_mapper_under_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
EVENT_MAPPER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = EVENT_MAPPER
SPEC.loader.exec_module(EVENT_MAPPER)

EventMapperState = EVENT_MAPPER.EventMapperState
map_audio_chunk_event = EVENT_MAPPER.map_audio_chunk_event
map_look_request_event = EVENT_MAPPER.map_look_request_event
map_model_interrupt_event = EVENT_MAPPER.map_model_interrupt_event
map_ready_event = EVENT_MAPPER.map_ready_event
map_server_event = EVENT_MAPPER.map_server_event
map_session_end_event = EVENT_MAPPER.map_session_end_event
map_session_update_event = EVENT_MAPPER.map_session_update_event
complete_output_turn = EVENT_MAPPER.complete_output_turn
map_transcript_in_event = EVENT_MAPPER.map_transcript_in_event
map_transcript_out_event = EVENT_MAPPER.map_transcript_out_event


class EventMapperTests(unittest.TestCase):
    def test_ready_event_matches_ios_contract(self) -> None:
        payload, state = map_ready_event(
            {
                "session_id": "session-1",
                "session_resume_token": "resume-1",
                "resumed": False,
                "model": "gemini-live",
            }
        )

        self.assertEqual(
            payload,
            {
                "type": "ready",
                "session_id": "session-1",
                "session_resume_token": "resume-1",
                "resumed": False,
                "model": "gemini-live",
            },
        )
        self.assertEqual(state, EventMapperState())

    def test_session_update_matches_ios_contract(self) -> None:
        payload, _ = map_session_update_event({"session_resume_token": "resume-2"})

        self.assertEqual(
            payload,
            {
                "type": "session_update",
                "session_resume_token": "resume-2",
            },
        )

    def test_transcript_in_synthesizes_finality_and_timestamp_keys(self) -> None:
        payload, _ = map_transcript_in_event(
            {
                "text": "hello",
                "final": True,
                "timestamp_ms": 111,
            }
        )

        self.assertEqual(
            payload,
            {
                "type": "transcript_in",
                "text": "hello",
                "is_final": True,
                "ts_ms": 111,
            },
        )

    def test_output_turn_id_is_generated_and_reused(self) -> None:
        state = EventMapperState()

        transcript_payload, state = map_transcript_out_event({"text": "hi there"}, state)
        audio_payload, state = map_audio_chunk_event({"pcm_b64": "AAE="}, state)
        interrupt_payload, state = map_model_interrupt_event({}, state)

        self.assertEqual(
            transcript_payload,
            {
                "type": "transcript_out",
                "text": "hi there",
                "turn_id": "turn-0001",
                "is_final": False,
            },
        )
        self.assertEqual(
            audio_payload,
            {
                "type": "audio_chunk",
                "pcm_b64": "AAE=",
                "sample_rate": 24_000,
                "turn_id": "turn-0001",
            },
        )
        self.assertEqual(
            interrupt_payload,
            {
                "type": "model_interrupt",
                "turn_id": "turn-0001",
            },
        )
        self.assertIsNone(state.active_turn_id)

    def test_complete_output_turn_advances_to_next_synthesized_turn(self) -> None:
        state = EventMapperState()

        first_payload, state = map_transcript_out_event({"text": "first"}, state)
        state = complete_output_turn(state)
        second_payload, state = map_transcript_out_event({"text": "second"}, state)

        self.assertEqual(first_payload["turn_id"], "turn-0001")
        self.assertEqual(second_payload["turn_id"], "turn-0002")
        self.assertEqual(state.active_turn_id, "turn-0002")

    def test_look_request_and_session_end_match_ios_contract(self) -> None:
        look_payload, _ = map_look_request_event(
            {"tool_call_id": "tool-2", "reason": "fresh visual context"}
        )
        end_payload, _ = map_session_end_event({"reason": "done"})

        self.assertEqual(
            look_payload,
            {
                "type": "look_request",
                "tool_call_id": "tool-2",
                "reason": "fresh visual context",
            },
        )
        self.assertEqual(
            end_payload,
            {
                "type": "session_end",
                "reason": "done",
            },
        )

    def test_dispatcher_routes_supported_event_types(self) -> None:
        payload, _ = map_server_event(
            "audio_chunk",
            {
                "audio": "AAE=",
                "sampleRate": 24_000,
                "turnId": "turn-9",
            },
        )

        self.assertEqual(
            payload,
            {
                "type": "audio_chunk",
                "pcm_b64": "AAE=",
                "sample_rate": 24_000,
                "turn_id": "turn-9",
            },
        )


if __name__ == "__main__":
    unittest.main()

# Product Requirements Document
## MetaGlasses × OmegaClaw — Agentic AR Assistant
**Version:** 0.1 (Hackathon Draft)  
**Date:** April 2026  
**Team Size:** 4 engineers  
**Time Budget:** 20 hours  
**Status:** In Scoping

---

## 1. Executive Summary

This project connects **OmegaClaw** (the agentic tool execution layer from Fetch.ai's uAgent ecosystem) to **Meta smart glasses** to create a hands-free AI assistant that can see, listen, and act. The user puts on their glasses, taps the AI button, and speaks a natural language request. A high-quality orchestration model (TBD) routes the request to either a **Gemini Live** vision/speech module or to **OmegaClaw** for real-world task execution via connected apps. Sub-agent tasks (parsing, formatting, confirmation) are handled by **Gemma** models running locally or on-device.

The primary demo scenario is a **multi-step agentic workflow**: the user speaks a request, the orchestrator decomposes it, delegates subtasks to OmegaClaw agents, and speaks a synthesized result back — all within a few seconds, hands-free.

---

## 2. Goals & Success Criteria

| Goal | Success Criteria |
|------|-----------------|
| End-to-end voice → action loop | User speaks a request; result is executed and spoken back within ~5 seconds |
| Multi-step orchestration (P0) | At least one demo showing a 2-step agentic chain (e.g., search → summarize → speak) |
| Vision awareness (P1) | "What am I looking at?" returns an accurate scene description via Gemini |
| Real-world task delegation (P1) | At least 2 OmegaClaw integrations working (e.g., web search + calendar) |
| Hackathon demo-readiness | Stable enough for a 3-minute live demo; graceful failure modes |

---

## 3. System Architecture

```
User Voice Input (glasses mic / phone mic)
        │
        ▼
┌─────────────────────────┐
│  Gemini Live            │  ← Speech-to-text, streaming audio
│  (on-device / edge)     │  ← Vision via glasses camera / phone camera
└────────────┬────────────┘
             │ Transcribed intent
             ▼
┌─────────────────────────┐
│  Orchestration Model    │  ← TBD (Claude / GPT-4o / Gemini 1.5 Pro)
│  (intent classification │
│   + task decomposition) │
└──────┬──────────┬───────┘
       │          │
       ▼          ▼
┌──────────┐  ┌──────────────────────┐
│  Gemini  │  │  OmegaClaw           │
│  Vision  │  │  (Fetch.ai uAgents)  │
│  Module  │  │                      │
└──────────┘  │  ┌────────────────┐  │
              │  │ Web Search     │  │
              │  │ Calendar Agent │  │
              │  │ Shopping List  │  │
              │  │ Messaging (P2) │  │
              │  └────────────────┘  │
              └──────────────────────┘
                       │
              ┌────────▼─────────┐
              │  Gemma Sub-Agent │  ← Response formatting, disambiguation
              └────────┬─────────┘
                       │
                       ▼
              Text-to-Speech → Glasses Speaker
```

### Component Responsibility Map

| Component | Role | Owner (suggested) |
|-----------|------|-------------------|
| Swift iOS app | UI shell, camera feed, audio I/O, API bridge | Engineer A |
| Gemini Live | STT, TTS, camera vision | Engineer A/B |
| Orchestration model (TBD) | Intent routing, task decomposition | Engineer B |
| OmegaClaw integration | Tool execution (search, calendar, lists) | Engineer C |
| Gemma sub-agents | Response cleaning, follow-up parsing | Engineer D |
| Phone-camera test harness | Phase 1 testing scaffold | All |

---

## 4. Phased Delivery Plan

### Phase 1 — Orchestration Validation via Phone (Hours 0–10)
Get the full agent loop working using the phone camera as a proxy for Meta Glasses. No hardware dependency. Goal is to validate that voice → orchestrator → OmegaClaw → response works end-to-end.

**Deliverables:**
- Swift app capturing phone camera feed and mic input
- Gemini Live integration for STT and vision queries
- Orchestrator calling OmegaClaw for at least one tool (web search)
- Audio response spoken back to user

### Phase 2 — Meta Glasses Integration (Hours 10–18)
Swap the phone camera feed for the Meta Glasses camera stream. Connect the audio I/O path to the glasses speaker/mic via the Meta SDK.

**Deliverables:**
- Meta Glasses SDK integrated into Swift app
- Camera + mic input routing switched to glasses hardware
- All Phase 1 functionality working through glasses

### Phase 3 — Polish & Demo Prep (Hours 18–20)
Stabilize the demo, add fallback handling, rehearse the 3-minute pitch flow.

**Deliverables:**
- At least 3 scripted demo scenarios tested end-to-end
- Graceful error messages for failed OmegaClaw calls
- README and demo script written

---

## 5. Feature Specifications

### 5.1 Multi-Step Agentic Workflow (P0 — Primary Demo)

**Description:** User speaks a request that requires more than one step to complete. The orchestrator decomposes the task, calls the appropriate OmegaClaw agents in sequence or parallel, and synthesizes a spoken response.

**Example flows:**
- "Find the best coffee shops near me and add the top result to my calendar for tomorrow at 10am"
  - Step 1: OmegaClaw web search agent → top 3 results
  - Step 2: Gemma sub-agent formats results, picks top result
  - Step 3: OmegaClaw calendar agent → creates event
  - Step 4: TTS confirms action
- "Search for flights to Tokyo next weekend and tell me the cheapest option"
  - Step 1: OmegaClaw web search
  - Step 2: Gemma parses and ranks results
  - Step 3: TTS speaks summary

**Acceptance criteria:**
- At least one 2-step chain demonstrated live
- Total round-trip latency under 8 seconds for 2-step chain
- Spoken confirmation includes result of both steps

---

### 5.2 Scene Description / Vision (P1)

**Description:** User asks "What am I looking at?" or "Describe what's in front of me." Gemini Live processes the current camera frame and speaks back a scene description.

**Example utterances:**
- "What am I looking at?"
- "Is this restaurant busy?"
- "What does this sign say?"

**Acceptance criteria:**
- Responds within 3 seconds of utterance
- Describes the primary subject(s) in the scene accurately
- Handles low-light and blurry frames gracefully (returns "I can't see clearly, try moving closer")

---

### 5.3 Web Search via OmegaClaw (P1)

**Description:** User asks a factual or local question. Orchestrator routes to OmegaClaw's web search agent. Gemma sub-agent summarizes results. TTS speaks back the answer.

**Example utterances:**
- "Search for the best coffee shops nearby"
- "What's the weather like this afternoon?"
- "Who won the game last night?"

**Acceptance criteria:**
- Returns spoken answer within 5 seconds
- Summary is under 3 sentences (Gemma formats for speech, not reading)

---

### 5.4 Calendar Scheduling via OmegaClaw (P1)

**Description:** User creates, checks, or modifies calendar events via voice.

**Example utterances:**
- "Add a dentist appointment tomorrow at 3pm"
- "What do I have going on Friday?"
- "Move my 2pm meeting to 4pm"

**Acceptance criteria:**
- Create event confirmed in connected calendar (Google or Apple)
- Read-back of schedule returns correct events
- Ambiguous time ("next week") prompts a clarifying question before acting

---

### 5.5 Shopping List / Reminders via OmegaClaw (P1)

**Description:** User adds items to a shopping list or creates reminders through a connected list app.

**Example utterances:**
- "Add milk and eggs to my shopping list"
- "Remind me to call the plumber when I get home"

**Acceptance criteria:**
- Items confirmed in connected list app within 3 seconds
- Multi-item requests ("milk, eggs, and bread") parsed correctly
- Spoken confirmation lists all added items

---

### 5.6 Messaging via OmegaClaw (P2 — Stretch)

**Description:** User sends messages to contacts through connected messaging apps (WhatsApp, Telegram, iMessage).

**Example utterances:**
- "Send a message to John saying I'll be late"
- "Reply to Sarah's last message with 'on my way'"

**Acceptance criteria:**
- Message sent to correct contact on correct platform
- Confirmation spoken back before sending (with 3-second cancel window)
- Only surfaces if time allows after P0/P1 are solid

---

### 5.7 Proactive Context Awareness (P2 — Stretch)

**Description:** Glasses passively observe the scene and surface relevant information without being asked.

**Example:** User is reading a menu → glasses say "The pasta here has strong reviews."

**Note:** Deprioritize for this hackathon. Requires always-on vision processing which may exceed latency and battery constraints in 20 hours.

---

## 6. Technical Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Mobile app | Swift (iOS) | Handles camera, mic, audio playback, API orchestration |
| Speech I/O | Gemini Live | Streaming STT + TTS; multimodal vision input |
| Orchestration | TBD (Claude / GPT-4o / Gemini 1.5 Pro) | Intent classification, task decomposition, tool routing |
| Tool execution | OmegaClaw (Fetch.ai uAgents) | Executes real-world tasks via registered agent network |
| Sub-agents | Gemma | Response formatting, disambiguation, result ranking |
| Glasses hardware | Meta smart glasses | Phase 2 only; Phase 1 uses phone camera |
| Phase 1 test harness | iPhone camera + Xcode simulator | Validates full orchestration loop before glasses |

**OmegaClaw Integration Notes:**
- OmegaClaw exposes tool-use capabilities as uAgents on the Fetch.ai Agentverse network
- The Swift app (or an intermediary Python service) calls the OmegaClaw endpoint with a structured task payload
- Confirmed available tools for this build: web search, calendar, shopping list/reminders
- Messaging tools (WhatsApp/Telegram/iMessage) to be validated during integration; treat as P2 until confirmed

---

## 7. Out of Scope (for this hackathon)

- On-device model inference (all models run via API)
- Custom wake word (use tap-to-activate)
- Multi-language support
- User authentication / account management
- Persistent conversation memory across sessions
- Android or non-Meta glasses hardware
- Always-on passive scene monitoring

---

## 8. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| OmegaClaw API latency too high for real-time feel | Medium | Cache common results; use optimistic spoken responses ("On it...") while waiting |
| Meta Glasses SDK integration takes longer than expected | Medium | Phase 1 phone-camera harness ensures demo works even if Phase 2 incomplete |
| Orchestration model picks wrong tool | Medium | Add explicit routing rules as system prompt guardrails for the 4 primary tools |
| Gemini Live STT struggles with background noise | Low | Test outdoors early; add push-to-talk fallback |
| OmegaClaw messaging integrations not available in time | Low | Messaging is P2; drop it cleanly if not confirmed by hour 10 |

---

## 9. Demo Script (3-minute Hackathon Pitch)

**Scene 1 — Vision (30s)**  
Put on glasses, tap AI button: *"What am I looking at?"* → Gemini describes the scene.

**Scene 2 — Simple delegation (30s)**  
*"Add oat milk to my shopping list"* → OmegaClaw confirms item added, spoken back.

**Scene 3 — Multi-step orchestration (90s) ← PRIMARY DEMO**  
*"Find a good sushi restaurant nearby and add it to my calendar for dinner on Friday"*  
→ OmegaClaw search returns results → Gemma picks top result → OmegaClaw calendar creates event → spoken confirmation of both steps.

**Scene 4 — Calendar query (30s)**  
*"What do I have going on this Friday?"* → Reads back events including the one just created.

---

## 10. Appendix — Useful Links

- Fetch.ai OmegaClaw / uAgent docs: [https://fetch.ai/docs](https://fetch.ai/docs)
- Gemini Live API: [https://ai.google.dev/gemini-api/docs/live](https://ai.google.dev/gemini-api/docs/live)
- Meta Glasses developer SDK: [https://developers.facebook.com/docs/ray-ban-meta-smart-glasses](https://developers.facebook.com/docs/ray-ban-meta-smart-glasses)
- Gemma model access: [https://ai.google.dev/gemma](https://ai.google.dev/gemma)
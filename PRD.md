# OmegaClaw Glasses Runtime
## OpenClaw-Style Agentic Assistant for Meta Ray-Ban Glasses

**OmegaClaw Skill Forge · Powered by Agentverse · Fetch.ai Prize Track**  
Version 2.0 | April 2026 | Team: 4 Engineers | Budget: 20 Hours

---

## 1. Executive Summary

OmegaClaw Glasses Runtime is a general-purpose, OpenClaw-style assistant for Meta Ray-Ban glasses. The product combines:

- a live multimodal interaction layer for low-latency voice and vision
- OmegaClaw as the planner, router, and delegation layer
- Agentverse skills as specialist capabilities

The core product goal is not "badge identification." The goal is "OpenClaw in glasses": the user speaks naturally, the glasses understand what the user wants in context, OmegaClaw decides whether to answer directly or delegate, and the result is returned as spoken audio.

The first flagship demo skill is `identify_person`. It is the first polished end-to-end example because it is easy to judge live. It is not the full boundary of the product.

Example requests the runtime should eventually support:

- "Who is this?"
- "What am I looking at?"
- "Summarize this booth."
- "Order the drink I'm holding."
- "Book a reservation here."
- "Send a message about what I just saw."

Important architectural note: OmegaClaw is the orchestration and delegation layer, not the live audio-video layer. For this build, Gemini Live remains the real-time multimodal session layer because it already solves low-latency voice, turn-taking, and visual context. OmegaClaw sits behind that live loop and decides which skill to invoke.

This project has two deliverables with equal weight:

1. a reusable OmegaClaw-to-Agentverse glasses runtime plus at least one working skill registration
2. a Meta glasses demo proving the runtime works in a real interaction flow

Current status honesty check: the repository is not yet a full replication of VisionClaw. It is a VisionClaw-compatible scaffold with the right client-server protocol shape, an iOS session shell, basic audio plumbing, and mock glasses support. The remaining work is to replace the backend echo server with a real Gemini Live bridge, wire continuous audio streaming, complete DAT camera integration, and connect OmegaClaw plus Agentverse end to end.

---

## 2. Product Goal

The product should be presented as a reusable glasses runtime with a stable delegation model:

- The glasses are the interface.
- The user speaks naturally.
- The runtime sees what the user sees.
- OmegaClaw decides whether direct response or specialist delegation is appropriate.
- Agentverse skills perform specialist work.
- The result comes back either as spoken audio or as a confirmed external action plus spoken status, depending on the task type.

The first flagship skill is `identify_person`, but the runtime should be designed so future skills can be added without redesigning the app architecture.

---

## 3. Prize Track Alignment

Prize: OmegaClaw Skill Forge powered by Agentverse. 1st: $1,500 / 2nd: $1,000.

Requirement: build a new specialist skill or capability for OmegaClaw using Agentverse, register it, and make it discoverable and invokable through OmegaClaw in a real interaction flow.

| Requirement | How We Meet It |
|-------------|----------------|
| Build a new specialist skill or capability | First flagship skill is `identify_person`, with the surrounding runtime designed for many future skills |
| Build a specialist agent for a specific use case | Python uAgent on Agentverse for person-context lookup |
| Register it on Agentverse | Agent registered via Agentverse dashboard with a stable address |
| Create the OmegaClaw integration layer | OmegaClaw routes requests from the glasses runtime to the registered skill |
| Allow OmegaClaw to discover, invoke, and use the agent | Skill is registered with metadata, schema, and routing hints |
| Demo the full interaction flow | User speaks through glasses, OmegaClaw delegates, result returns as spoken audio |

Why this is strong for judging:

- It shows a real specialist skill working end to end.
- It also shows a reusable architecture instead of a one-off demo.
- It aligns directly with the Agentverse routing and delegation story in the brief.

OmegaClaw docs context incorporated into this PRD:

- the docs index describes OmegaClaw docs as tutorials plus reference pages, including channels, remote Agentverse skills, and internals extension points
- Tutorial 04 defines the intended channel-adapter pattern
- Tutorial 06 defines the intended remote Agentverse skill pattern
- the extension-points reference confirms that adding a channel, adding a skill, and adding a remote skill are first-class extension seams in OmegaClaw

---

## 4. VisionClaw Parity Status

The repo should currently be described as scaffold-level, not full parity.

Already present:

- iOS app shell
- WebSocket message protocol
- mic capture
- PCM playback
- mock glasses mode
- photo resizing
- debug UI

Partially present:

- DAT glasses abstraction
- backend session lifecycle shape
- tool event message schema
- look-request handling on the client

Missing for parity:

- real Gemini Live proxy
- continuous audio streaming loop
- live transcripts and streamed model audio
- actual DAT still capture and optional frame access
- real tool dispatch
- OmegaClaw invocation
- Agentverse invocation
- interruption and look flow verified end to end on device

Bottom line: this is a VisionClaw-compatible scaffold, not a full VisionClaw replication, until the checklist in Section 11 is complete.

---

## 5. System Architecture

### 5.1 Runtime Layers

The runtime should be understood as five layers:

1. User Interface Layer  
   Meta Ray-Ban glasses plus iPhone shell.

2. Live Interaction Layer  
   Gemini Live handles low-latency audio, turn-taking, vision context, transcripts, and speech output.

3. Orchestration Layer  
   OmegaClaw receives structured task context and decides whether to answer directly, ask a follow-up, or delegate.

4. Skill Layer  
   Registered Agentverse skills perform specialist work.

5. Safety Layer  
   Confirmation, timeout handling, fallback behavior, and execution guardrails.

### 5.2 General Data Flow

```
User speaks naturally while looking at the world

1. Voice + image context -> Gemini Live session
2. Gemini Live understands request + scene context
3. Gemini Live sends structured task context -> OmegaClaw
4. OmegaClaw chooses one of four paths:
   a. answer directly
   b. ask a follow-up question
   c. invoke an inform skill
   d. invoke an act skill that later requires confirmation
5. If delegated, OmegaClaw invokes the matching Agentverse capability
6. Skill returns structured result, preview, or status
7. OmegaClaw returns result to Gemini Live
8. Gemini Live speaks the final answer, clarification, or confirmation prompt
```

### 5.3 First Flagship Inform Skill Example

The first polished demo skill is `identify_person`.

```
User: "Who is this?"

1. Gemini Live hears the question and sees a visible badge
2. Gemini extracts name, organization, and title
3. OmegaClaw classifies task as identify_person
4. OmegaClaw invokes the registered Agentverse skill
5. Skill returns summary + confidence
6. Gemini speaks a short contextual answer
```

### 5.4 Future Action Skill Example

The same runtime should also support action-taking skills.

```
User: "Order the drink I'm holding on Amazon"

1. Gemini Live hears the purchase intent and sees product packaging
2. OmegaClaw classifies task as purchase_item
3. OmegaClaw invokes a purchase skill
4. Skill returns preview:
   item, merchant, price, quantity, destination
5. Glasses ask for explicit confirmation
6. User says yes
7. OmegaClaw executes the action
8. Glasses speak final status
```

Without confirmation, the system is only answering, not acting.

### 5.5 Component Map

| Component | Technology | Where It Lives | Owner |
|-----------|-----------|----------------|-------|
| iOS Glasses App | Swift, Meta DAT SDK, AVFoundation | VisionClaw-derived app | A |
| Live Interaction Layer | Gemini Live API | backend live bridge | A/B |
| Session Protocol | WebSocket JSON | iOS + backend | A/C |
| OmegaClaw Bridge | HTTP | backend to OmegaClaw | C |
| OmegaClaw Orchestration Layer | ASI1 / OmegaClaw Gateway | hosted endpoint | C |
| Skill Registry | OmegaClaw skill config | OmegaClaw registry | C |
| Agentverse Skill | Python, uAgents SDK, FastAPI | hosted agent | C/D |
| Safety Layer | confirmation, timeouts, fallbacks | backend + prompt logic | B/C |

---

## 6. Runtime Contract

Every skill added to the runtime should follow the same contract so the app architecture does not change every time a new capability is added.

Required skill contract:

- `skill_name`: stable unique identifier
- `skill_type`: `inform` or `act`
- `description`: one-sentence purpose
- `discovery_metadata`: trigger phrases, examples, tags, domain hints
- `input_schema`: exact structured input fields
- `output_schema`: exact structured output fields
- `confirmation_policy`: whether explicit confirmation is required
- `timeout_ms`: maximum runtime before fallback
- `failure_behavior`: short user-facing fallback

Runtime guarantees:

- The live layer always speaks to the user in natural language.
- OmegaClaw always routes using the same dispatch path.
- Skills only exchange structured data with OmegaClaw.
- New skills should be addable by registration and backend support, not by redesigning the glasses UI.

### 6.1 Skill Types

- `inform`: returns information only
- `act`: performs an external effect after explicit confirmation

Examples:

- `identify_person`
- `scene_explain`
- `purchase_item`
- `book_reservation`
- `send_contextual_message`

### 6.2 Routing And Delegation Policy

OmegaClaw should apply the same routing policy to every incoming request:

1. Understand user request from live audio plus visual context.
2. Decide whether the request can be answered directly.
3. If ambiguous, ask a short follow-up question.
4. If delegation is needed, rank available skills by intent fit, schema fit, and expected latency.
5. If best match is `inform`, invoke it and summarize the result.
6. If best match is `act`, request a preview, speak it, and wait for explicit confirmation before execution.
7. If no skill matches with enough confidence, say the capability is unavailable rather than fabricate a result.

This routing layer is the heart of the "OpenClaw in glasses" behavior. The user should experience one assistant, even though multiple specialist skills may exist behind the scenes.

### 6.3 Future Skill Examples

To make extensibility concrete, the PRD should explicitly name future skills:

- `scene_explain`: summarize what the user is looking at
- `purchase_item`: identify and buy a visible item
- `event_lookup`: read a badge, poster, or booth sign and return event context
- `book_reservation`: delegate booking after previewing time and place
- `send_contextual_message`: draft or send a message based on what the user sees and says

Only one of these needs to be polished for the prize demo. The point is to show a reusable runtime, not a one-off badge reader.

### 6.4 OmegaClaw-Core Extension Model

This PRD follows the extension model documented in OmegaClaw-Core:

- add a local skill by declaring it in `src/skills.metta`
- add a remote skill by exposing a local MeTTa skill whose body delegates to the Python bridge in `src/agentverse.py`
- add a channel by creating a Python adapter in `channels/` and wiring it into `src/channels.metta`

This matters because the runtime should integrate with OmegaClaw using its intended seams rather than bypassing the agent loop with custom side paths.

---

## 7. Live Layer Assumption

As of this PRD version, we assume OmegaClaw does not provide a public Gemini-Live-style real-time multimodal session layer for continuous audio plus camera input.

Therefore:

- Gemini Live remains the low-latency session layer.
- OmegaClaw remains the reasoning, discovery, routing, and delegation layer.
- If Fetch.ai provides a hackathon-only real-time OmegaClaw interface, we can evaluate swapping later, but it is not a dependency for the prize-track submission.

---

## 8. First Flagship Skill

This section describes the first flagship skill because the hackathon needs one polished capability that judges can see working end to end. It is the first implementation of the broader runtime, not the full boundary of the product.

### 8.1 Skill Overview

- Skill name: `identify_person`
- Skill type: `inform`
- Purpose: identify a visible name badge and return a short spoken professional summary
- Input: `{ name, organization, title }`
- Output: `{ summary, confidence, source }`
- Latency target: under 3 seconds from skill receipt to skill response

### 8.2 Agent Implementation

The first flagship skill is a Python uAgent on Agentverse, wrapped in FastAPI for OmegaClaw integration.

OmegaClaw-Core tutorial context: remote Agentverse skills are expected to follow a simple pattern where a local MeTTa skill calls into the Python Agentverse bridge and that bridge sends the request to a fixed remote Agentverse address. This PRD adopts that same pattern for the first flagship skill.

Suggested file structure:

```text
flagship-skill/
  agent.py
  context_service.py
  models.py
  main.py
  requirements.txt
  .env
```

Responsibilities:

- `agent.py`: uAgent definition and Agentverse registration
- `context_service.py`: person-context lookup logic
- `models.py`: request and response schemas
- `main.py`: HTTP bridge for OmegaClaw

### 8.3 Agentverse Registration

1. Create the agent with a deterministic seed.
2. Run locally and capture the stable agent address.
3. Make the endpoint publicly reachable.
4. Register on Agentverse.
5. Add metadata and schema.
6. Verify discoverability.
7. Store the registered address for OmegaClaw skill registration.

### 8.4 Public Reachability

Preferred hosting options:

- Railway
- Render
- Fly.io or Cloud Run if already familiar
- ngrok only as a last-resort hackathon fallback

Always test from an external network before relying on the endpoint.

---

## 9. OmegaClaw Integration

OmegaClaw is the integration layer that tells the runtime how to discover and invoke the registered skill.

### 9.1 First Skill Config Concept

```json
{
  "skill_name": "identify_person",
  "skill_type": "inform",
  "description": "Identify a person from a visible badge and return short professional context.",
  "trigger_phrases": [
    "who is this",
    "identify this person",
    "who am I looking at",
    "tell me about this person"
  ],
  "agent_address": "agent1qYOUR_AGENT_ADDRESS_HERE",
  "input_schema": {
    "name": "string",
    "organization": "string",
    "title": "string"
  },
  "output_schema": {
    "summary": "string",
    "confidence": "string"
  },
  "timeout_ms": 5000
}
```

### 9.2 Action Skill Config Concept

```json
{
  "skill_name": "purchase_item",
  "skill_type": "act",
  "description": "Purchase a user-confirmed visible item.",
  "requires_confirmation": true,
  "requires_account_link": true,
  "pre_execution_preview": {
    "item": "string",
    "merchant": "string",
    "price": "string",
    "quantity": "integer",
    "destination": "string"
  },
  "execution_result_schema": {
    "status": "success | failed | cancelled",
    "order_id": "string",
    "eta": "string"
  }
}
```

### 9.3 Action Execution Requirements

If a skill can take action in the outside world:

- require linked account or permission
- return a preview before execution
- require explicit spoken confirmation
- fail closed on ambiguity
- return final status, not just text
- log confirmation state and downstream result

### 9.4 Channel Adapter Integration

OmegaClaw-Core tutorial and reference docs make the intended communication extension point explicit: new communication surfaces should usually be implemented as channel adapters, not as subordinate agents with their own separate reasoning loops.

Authoritative OmegaClaw-Core pattern:

- adapters live in `channels/`
- MeTTa-side dispatch lives in `src/channels.metta`
- the runtime chooses the active adapter via `commchannel`
- each adapter exposes:
  - `start_<name>(...)`
  - `getLastMessage()`
  - `send_message(str)`

For this project, the glasses backend should be treated as a first-class channel when integrating into OmegaClaw's main loop. That means:

- create a backend adapter module under `channels/`
- wire it into `initChannels`, `(receive)`, and `(send $msg)` in `src/channels.metta`
- declare any new runtime parameters with `(= (MY_*) (empty))` and bind them through `configure`

This preserves one clean agentic loop and matches OmegaClaw-Core Tutorial 04 plus the channels reference.

### 9.5 Remote Agentverse Skill Pattern

OmegaClaw-Core Tutorial 06 documents the intended remote-skill pattern:

1. OmegaClaw calls a local MeTTa skill.
2. That skill delegates into the Python Agentverse bridge in `src/agentverse.py`.
3. The bridge sends the request to a fixed Agentverse address.
4. OmegaClaw receives the reply as normal tool output.

This PRD adopts that exact conceptual pattern for the first flagship skill and for future remote skills.

### 9.4 Channel Adapter Integration

If the underlying OpenClaw or OmegaClaw stack expects extensions to arrive through channels rather than standalone subordinate agents, the recommended implementation path is a custom backend channel adapter.

Why this matters:

- it keeps one agentic loop instead of creating a second competing loop
- it treats the glasses backend as a first-class channel
- it allows backend messages to flow through the full reasoning pipeline
- it avoids duplicating orchestration logic outside the runtime

Recommended adapter shape:

```python
def start_my_backend(config_param1, config_param2, auth_secret=None):
    # Connect to your backend
    # Start a thread, poller, or listener for incoming messages
    pass

def getLastMessage():
    # Return the latest backend message for the agent loop
    pass

def send_message(text):
    # Send the agent response back to your backend
    pass
```

Recommended wiring pattern in `src/channels.metta`:

- add the new backend channel to `initChannels`
- configure `commchannel` to `my_backend` when this runtime is active
- update `(receive)` so it dispatches to `my_backend.getLastMessage`
- update `(send)` so it dispatches to `my_backend.send_message`

Conceptual dispatch pattern:

```metta
(= (initChannels)
   (progn
      (println! "Initializing channels")
      (configure commchannel my_backend)
      (if (== (commchannel) my_backend)
          (py-call (my_backend.start_my_backend ...)))))
```

```metta
(= (receive)
   (if (== (commchannel) irc)
       (py-call (irc.getLastMessage))
       (if (== (commchannel) mattermost)
           (py-call (mattermost.getLastMessage))
           (py-call (my_backend.getLastMessage)))))
```

The design intent is clear: the glasses backend should be integrated as a channel, not as a second standalone agent. That preserves one clean reasoning loop and matches the intended extension point for channel-based integrations.

---

## 10. Prompt And UX Rules

The system prompt should define the runtime first and the current flagship skill second.

Required prompt behaviors:

- speak naturally because the user cannot see a screen
- answer directly when no skill is needed
- ask a short follow-up when ambiguous
- delegate when a specialist skill is needed
- never execute actions without explicit spoken confirmation
- treat `identify_person` as one available skill, not the only skill

Flagship skill rules:

- if the user asks "Who is this?" and a badge is visible, extract badge fields and call `identify_person`
- if the badge is unreadable, ask the user to move closer
- if no badge is visible, say so clearly
- keep final spoken result short and natural

---

## 11. Delivery Plan

### 11.1 VisionClaw Parity Checklist

The project should only claim VisionClaw-equivalent capability when all items below are green:

| Capability | Current Status | Requirement For Parity |
|------------|----------------|------------------------|
| Session protocol | Present | stable during backend upgrade |
| iOS session shell | Present | works against real backend messages |
| Mic capture | Present | streams continuously during live session |
| PCM playback | Present | reliable streamed playback plus interruption |
| Backend live model bridge | Missing | Gemini Live session proxy replaces echo backend |
| Input transcripts | Missing end to end | backend emits real transcript events |
| Output transcripts | Missing end to end | backend emits partial and final model transcript events |
| Tool dispatch | Missing | backend routes model tool calls into OmegaClaw |
| Look request loop | Partial | backend requests images and consumes them correctly |
| OmegaClaw integration | Missing | real request-response path |
| Agentverse integration | Missing | registered skill invoked successfully |
| DAT still capture | Partial | paired glasses capture real images |
| End-to-end spoken response | Missing | speech -> routing -> spoken reply works on device |

### 11.2 Phases

| Phase | Hours | Goal | Gate |
|-------|-------|------|------|
| 0: Scaffold Validation | 0-2 | verify current app and backend shell | iOS app connects to `/session` and debug controls work |
| 1: Live Bridge | 2-6 | replace echo backend with Gemini Live bridge | user speech produces transcript and audio reply |
| 2: Tool Path | 6-10 | route first flagship skill through OmegaClaw to Agentverse | user asks for flagship skill and gets spoken result |
| 3: Hardware Path | 10-16 | replace mock capture with real glasses capture | same flagship flow works on glasses hardware |
| 4: Polish And Demo Prep | 16-20 | rehearse, harden failure handling, produce judging artifacts | dry run passes reliably |

### 11.3 Ordered Plan

1. Validate the current scaffold on device.
2. Replace the echo backend with a real Gemini Live bridge.
3. Add backend-side tool dispatch into OmegaClaw and onward into Agentverse.
4. Verify the first flagship skill on iPhone.
5. Replace placeholder DAT capture with real glasses capture.
6. Only then spend time on optional action-taking skills.

### 11.4 Checklists

Phase 0:

- run current iOS app on physical iPhone
- confirm `/session` connection
- confirm mock glasses path works
- confirm audio initialization
- verify current backend is still scaffold-level
- read OmegaClaw-Core Tutorial 04, Tutorial 06, the channels reference, and the extension-points reference before locking integration design

Phase 1:

- replace echo backend with Gemini Live coordinator
- forward audio, text, and photo events
- emit transcripts, audio chunks, look requests, and interrupts
- verify one complete speech round-trip

Phase 2:

- deploy first flagship Agentverse skill
- register skill in OmegaClaw
- add backend-side tool dispatch
- return skill result through Gemini Live as speech
- test unreadable input, no matching skill, and timeout behavior

Phase 3:

- connect Meta glasses
- replace placeholder DAT capture
- verify audio routing with no echo
- run same flagship flow on hardware

Phase 4:

- rehearse multiple clean demo runs
- test degraded-mode responses
- prepare screenshots, agent details, skill registration, and demo video
- update README with runtime architecture plus first-skill setup

---

## 12. Risks And Mitigations

The risks should be interpreted through the runtime-first lens: the main risk is not that one badge demo fails, but that the general live-routing-delegation stack is incomplete or unreliable.

| Risk | Severity | Mitigation |
|------|----------|-----------|
| OmegaClaw skill registration format is unclear | Critical | confirm exact format with Fetch.ai on day 1 |
| Agentverse endpoint is not externally reachable | Critical | deploy early and test from external network |
| Gemini Live bridge is unstable | Critical | make this the first implementation priority |
| DAT glasses integration slips | High | keep iPhone fallback path working |
| OmegaClaw endpoint format differs from expectation | High | confirm endpoint and auth before coding integration |
| Flagship skill quality is weak | Medium | choose well-known public examples for demo |
| Latency is too high | Medium | measure early, add spoken acknowledgment while waiting |
| Action-skill safety is underspecified | Medium | keep action skills conceptual unless confirmation path is implemented |

---

## 13. Demo Strategy

The pitch should start with the product, not the flagship skill.

Narrative rule:

- Start by describing the system as "OpenClaw in glasses."
- Explain that OmegaClaw can discover and invoke many specialist skills.
- Show one polished skill end to end because judges need a crisp demo.
- End by naming future skills the same runtime can support.

### 13.1 Demo Script

| # | Scene | Duration | User Says | Expected Output |
|---|-------|----------|-----------|-----------------|
| 1 | Product framing | 20s | narrator introduces "OpenClaw in glasses" | judges understand runtime concept |
| 2 | Live perception check | 20s | "What do I see?" | runtime describes visible scene |
| 3 | Flagship skill demo | 60s | "Who is this?" | runtime delegates to `identify_person` and speaks result |
| 4 | Failure handling | 20s | unreadable or blank scene | runtime gives graceful fallback |
| 5 | Platform wrap | 20s | narrator explains future skills | judges see extensibility |

### 13.2 Demo Props

The polished live demo can still use printed badges because they are reliable and legible, but the product narrative must remain runtime-first rather than badge-first.

---

## 14. Engineer Assignments

Assignments should be interpreted as runtime responsibilities first, with the flagship skill used only as the first end-to-end proof.

| Engineer | Primary Role | Focus |
|----------|-------------|-------|
| A | iOS app and hardware | session shell, audio, DAT integration |
| B | live prompt and UX | prompt behavior, runtime UX, fallback wording |
| C | backend and OmegaClaw integration | live bridge, tool dispatch, skill registration |
| D | Agentverse skill and QA | flagship skill service, deployment, external verification |

---

## 15. Latency Budget

This latency budget is for the first flagship skill, not every possible future skill.

| Step | Target |
|------|--------|
| Voice to Gemini Live | <500ms |
| Intent and scene understanding | <1s |
| Spoken acknowledgment | <500ms |
| OmegaClaw routing | <1s |
| Flagship skill execution | <2s |
| Return trip to live layer | <500ms |
| Speech synthesis output | <1s |
| Total | <7s |

---

## 16. Out Of Scope

- replacing Gemini Live with an unverified OmegaClaw real-time layer
- claiming full VisionClaw parity before the checklist is complete
- redesigning the runtime for every new skill
- fully productionized commerce flows across many merchants
- persistent memory across sessions
- Android build
- multi-language support
- passive always-on identification
- facial recognition

---

## 17. Build Readiness Checklist

The current PRD is strong enough to guide product direction, but the team should not assume the system will work end to end without validating the specific upstream integration points.

Before implementation is considered locked, the team must verify the following:

### 17.1 VisionClaw Reference Validation

We are using VisionClaw as the architectural baseline, so we should confirm the exact upstream extension points rather than rely only on high-level similarities.

Must verify:

- which parts of VisionClaw are reusable as-is versus only inspirational
- exact file and module layout for the live session path
- how VisionClaw handles Gemini Live session lifecycle
- how VisionClaw handles tool dispatch, look requests, and streamed audio
- whether there are any repo-specific assumptions about camera, audio, or transport that our runtime must preserve

Expected output of this verification:

- a short mapping of "VisionClaw upstream component" -> "our runtime equivalent"
- a list of files we intend to mirror, wrap, or replace

### 17.2 OpenClaw Or OmegaClaw Integration Contract Validation

The runtime should verify the exact intended extension point for the orchestration layer.

Must verify:

- whether the correct integration path is a custom channel adapter
- exact adapter file location and naming convention
- exact required adapter methods and threading or polling model
- exact `channels.metta` hooks for `initChannels`, `receive`, and `send`
- whether any additional registration or configuration is required for the new backend channel

Expected output of this verification:

- one confirmed integration contract for the backend channel adapter
- one implementation plan for wiring the adapter into the existing agent loop

### 17.3 Backend Loop Validation

The repo currently contains scaffold-level backend behavior, so the team must validate the real runtime loop before building higher-level skill features.

Must verify:

- how the backend will open and maintain the Gemini Live session
- how continuous mic audio is streamed from iOS to backend
- how transcripts and audio chunks are streamed back to iOS
- how tool calls are intercepted and routed to OmegaClaw
- how look requests trigger fresh photo capture and return images back into the loop
- how interruption and barge-in are handled

Expected output of this verification:

- one backend sequence diagram
- one message-flow checklist covering audio in, transcripts, tool calls, look requests, and audio out

### 17.4 Action Path Validation

The PRD now supports real-world actions conceptually. If the product is expected to do rather than only say, the action path must be validated explicitly.

Must verify:

- account-linking requirements for any action-capable skill
- confirmation and preview UX before execution
- how execution adapters actually call downstream systems
- what data must be logged for debugging and trust
- what the failure and cancellation states are
- which action skills are realistic for hackathon scope versus future scope

Expected output of this verification:

- one minimum viable action-skill design
- one explicit list of what is demoable now versus what stays future-facing

### 17.5 Hardware Validation

The runtime should not assume that mock-glasses behavior will translate directly to real Meta glasses hardware.

Must verify:

- DAT still capture from paired glasses
- optional frame access if needed by the interaction model
- mic and speaker routing
- audio-session stability with no echo or feedback
- latency differences between iPhone-only and glasses-connected modes

Expected output of this verification:

- one hardware readiness checklist
- one fallback plan if glasses hardware is unstable

### 17.6 Build Gate

Before the team says "this is ready to build," all of the following should be true:

- VisionClaw reference mapping is written down
- backend channel adapter contract is confirmed
- backend live-loop design is confirmed
- first flagship skill integration path is confirmed
- action path scope is explicitly bounded
- hardware fallback strategy is documented

If any of those are missing, the correct status is "direction is good, implementation assumptions still need validation."

---

## 18. Appendix

### 18.1 Useful Links

- VisionClaw repo: https://github.com/Intent-Lab/VisionClaw
- OmegaClaw docs index: https://github.com/asi-alliance/OmegaClaw-Core/blob/main/docs/README.md
- OmegaClaw channel tutorial: https://github.com/asi-alliance/OmegaClaw-Core/blob/main/docs/tutorial-04-adding-a-channel.md
- OmegaClaw remote Agentverse tutorial: https://github.com/asi-alliance/OmegaClaw-Core/blob/main/docs/tutorial-06-remote-agentverse-skills.md
- OmegaClaw channel reference: https://github.com/asi-alliance/OmegaClaw-Core/blob/main/docs/reference-channels.md
- OmegaClaw extension points: https://github.com/asi-alliance/OmegaClaw-Core/blob/main/docs/reference-internals-extension-points.md
- Agentverse: https://agentverse.ai
- Fetch.ai docs: https://fetch.ai/docs
- Gemini Live API: https://ai.google.dev/gemini-api/docs/live
- Meta DAT SDK: https://developers.facebook.com/docs/ray-ban-meta-smart-glasses

### 18.2 Key Principle

If the team ever has to choose between:

- making the runtime story clearer
- or adding more one-off badge-specific polish

choose the runtime story first.

# ContextLens
## Visual Person Intelligence for Meta Ray-Ban Glasses

**OmegaClaw Skill Forge · Powered by Agentverse · Fetch.ai Prize Track**  
Version 1.0 | April 2026 | Team: 4 Engineers | Budget: 20 Hours

---

## 1. Executive Summary

ContextLens is a specialist OmegaClaw skill powered by a custom Agentverse uAgent that gives Meta Ray-Ban glasses the ability to identify people from their name badges and speak back contextual intelligence about them in real time.

The user looks at someone wearing a name badge at a conference or hackathon, taps the AI button, and says 'Who is this?' The glasses camera captures a JPEG frame, Gemini extracts the name and organization via vision, and the request is routed through OmegaClaw to our registered Agentverse agent. The agent queries web and professional data sources, composes a 2-sentence context summary, and speaks it back through the glasses speaker within 5 seconds. No phone, no typing, no breaking conversation.

This project has two deliverables with equal weight: (1) the Agentverse uAgent + OmegaClaw skill registration, which is the prize track submission, and (2) the Meta glasses AR demo, which is the proof it works in a real context. The glasses app is built on the VisionClaw open-source repo (Intent-Lab/VisionClaw) to avoid rebuilding solved infrastructure.

Why this wins the Fetch.ai prize track: it builds a genuinely new specialist skill that does not exist in OmegaClaw's current 56+ library, it uses the Agentverse agent registration flow exactly as the brief requires, and the AR demo makes the value proposition immediately obvious to any judge in under 10 seconds.

---

## 2. Prize Track Alignment

Prize: OmegaClaw Skill Forge powered by Agentverse. 1st: $1,500 / 2nd: $1,000.

Requirement: Build a new specialist skill/capability for OmegaClaw using Agentverse. This means building a specialist agent for a specific use case, registering it on Agentverse, and creating the OmegaClaw skill or integration layer that allows OmegaClaw to discover, invoke, and use that agent.

| Requirement | How We Meet It |
|-------------|----------------|
| Build a new specialist skill/capability | Visual person identification from name badge + web context lookup. Not in OmegaClaw's existing 56 skills. |
| Build a specialist agent for a specific use case | Python uAgent deployed on Agentverse. Receives extracted name + org, returns structured person context. |
| Register it on Agentverse | Agent registered via Agentverse dashboard with a unique agent address. Discoverable by OmegaClaw. |
| Create the OmegaClaw skill/integration layer | OmegaClaw skill definition that maps the 'identify_person' intent to our Agentverse agent endpoint. |
| Allow OmegaClaw to discover, invoke, and use the agent | Skill registered in OmegaClaw skill library. Invoked via standard OmegaClaw tool call routing. |
| Demo with real use case | Live demo on hackathon floor: glasses see a name badge, agent identifies the person, result spoken back. |

---

## 3. System Architecture

### 3.1 Full Data Flow

```
User: 'Who is this?' + glasses camera sees name badge

1. JPEG frame (~1fps) + voice audio --> GeminiLiveService.swift (WebSocket)

2. Gemini Live (Google API)
   - Hears 'Who is this?'
   - Sees current JPEG frame
   - Extracts: name, organization, title from badge via vision
   - Fires tool call: identify_person({name, organization, title})

3. ToolCallRouter.swift --> OpenClawBridge.swift
   POST https://omegaclaw-gateway/v1/chat/completions
   { task: 'Identify person: [Name], [Org], [Title]' }

4. OmegaClaw Gateway
   - Matches task to registered 'identify_person' skill
   - Invokes our Agentverse agent via uAgent protocol

5. Agentverse uAgent (our Python FastAPI service)
   - Receives: name, organization, title
   - Queries: Gemini API (web grounding) for public context
   - Returns: { summary: '2-sentence context', confidence: high/low }

6. OmegaClaw returns result to OpenClawBridge

7. Gemini synthesizes spoken response
   'That's Sarah Chen, CTO at Fetch.ai. She leads the Agentverse
    platform and was previously at DeepMind.'

8. AudioManager plays PCM audio through glasses speaker
```

### 3.2 Component Map

| Component | Technology | Where It Lives | Owner |
|-----------|-----------|----------------|-------|
| iOS Glasses App | Swift, Meta DAT SDK, AVFoundation | VisionClaw repo (fork) | A |
| Gemini Live Service | WebSocket, Gemini Live API | GeminiLiveService.swift | A/B |
| Vision OCR + Tool Call | Gemini vision + function calling | GeminiConfig.swift system prompt | B |
| OmegaClaw Bridge | HTTP POST, Swift URLSession | OpenClawBridge.swift | C |
| OmegaClaw Skill Definition | OmegaClaw skill config (JSON/YAML) | OmegaClaw skill registry | C |
| Agentverse uAgent | Python, uAgents SDK, FastAPI | Hosted on Agentverse | C/D |
| Person Context Service | Gemini API (web grounding), Python | Inside uAgent | C/D |
| Agentverse Registration | Agentverse dashboard + CLI | fetch.ai/agentverse | C |

---

## 4. The Agentverse uAgent — Prize Track Deliverable

This section is the most important in the PRD. The Agentverse agent is what gets judged. Build this first, demo second.

### 4.1 Agent Specification

- Agent name: ContextLens Person Intelligence Agent
- Agent type: Specialist uAgent registered on Fetch.ai Agentverse
- Input: `{ name: string, organization: string, title: string }`
- Output: `{ summary: string (max 2 sentences), confidence: 'high' | 'low', source: string }`
- Latency target: <3s from receipt of input to response

### 4.2 Agent Implementation

The agent is a Python service using the uAgents SDK, wrapped in FastAPI for the HTTP layer that OmegaClaw calls.

**File Structure**

```
contextlens-agent/
  agent.py           # uAgent definition, message handlers, Agentverse registration
  context_service.py # Gemini API calls for person context lookup
  models.py          # Pydantic models for input/output
  main.py            # FastAPI app entry point
  requirements.txt   # uagents, fastapi, uvicorn, google-generativeai
  .env               # GEMINI_API_KEY, AGENT_SEED
```

**agent.py**

```python
from uagents import Agent, Context, Model
from context_service import get_person_context

class PersonQuery(Model):
    name: str
    organization: str
    title: str

class PersonContext(Model):
    summary: str
    confidence: str  # 'high' or 'low'
    source: str

agent = Agent(
    name='contextlens-person-intelligence',
    seed='YOUR_AGENT_SEED_PHRASE',  # deterministic address
    port=8001,
    endpoint=['http://YOUR_HOST:8001/submit']
)

@agent.on_message(model=PersonQuery)
async def handle_query(ctx: Context, sender: str, msg: PersonQuery):
    result = await get_person_context(msg.name, msg.organization, msg.title)
    await ctx.send(sender, PersonContext(**result))

if __name__ == '__main__':
    agent.run()
```

**context_service.py**

```python
import google.generativeai as genai
import os

genai.configure(api_key=os.environ['GEMINI_API_KEY'])
model = genai.GenerativeModel('gemini-1.5-flash')

async def get_person_context(name: str, org: str, title: str) -> dict:
    prompt = f'''
    Person: {name}
    Organization: {org}
    Title: {title}

    In exactly 2 sentences, describe who this person is and what they are known for.
    Focus on their professional role and most notable achievement or project.
    If you cannot find reliable information, say so in 1 sentence.
    Do not mention sources. Write for spoken audio, not reading.
    '''
    response = model.generate_content(prompt)
    text = response.text.strip()
    confidence = 'low' if any(w in text.lower() for w in ['cannot', 'not find', 'unclear', 'no information']) else 'high'
    return { 'summary': text, 'confidence': confidence, 'source': 'gemini-web-grounding' }
```

**main.py (FastAPI bridge for OmegaClaw HTTP calls)**

```python
from fastapi import FastAPI
from models import PersonQuery, PersonContext
from context_service import get_person_context

app = FastAPI()

@app.post('/v1/chat/completions')
async def completions(request: dict):
    task = request['messages'][-1]['content']
    name, org, title = parse_task(task)
    result = await get_person_context(name, org, title)
    return {
        'choices': [{
            'message': { 'role': 'assistant', 'content': result['summary'] }
        }]
    }

def parse_task(task: str) -> tuple:
    # Task format: 'Identify person: [Name], [Org], [Title]'
    parts = task.replace('Identify person: ', '').split(', ')
    name = parts[0] if len(parts) > 0 else 'Unknown'
    org = parts[1] if len(parts) > 1 else 'Unknown'
    title = parts[2] if len(parts) > 2 else 'Unknown'
    return name, org, title
```

### 4.3 Agentverse Registration Steps

This is a sequential checklist. Do not skip steps. Complete this by end of hour 4.

1. Install uAgents SDK: `pip install uagents`
2. Create agent with deterministic seed (generates a stable agent address)
3. Run agent locally: `python agent.py` — note the agent address printed on startup (`agent1q...`)
4. Go to https://agentverse.ai — create account if needed
5. Register agent: Agents > Create Agent > Hosted or Remote
   - For hackathon: use Remote agent (your FastAPI endpoint, publicly reachable)
   - Enter your ngrok or cloud URL as the endpoint
6. Add agent metadata: name, description, input/output schema
7. Verify agent is discoverable: search for 'contextlens' in Agentverse explorer
8. Note the agent address — you need it for the OmegaClaw skill config

### 4.4 Making the Agent Publicly Reachable (Hackathon Environment)

The Agentverse needs to reach your FastAPI endpoint. Options in order of preference:

- **Option A (recommended):** Deploy to a free cloud host. Railway.app or Render.com can deploy a FastAPI app from GitHub in under 10 minutes. Free tier is sufficient for hackathon traffic.
- **Option B:** ngrok tunnel from a local machine. Run: `ngrok http 8001`. Use the https ngrok URL as your Agentverse endpoint. Risk: if the machine sleeps or ngrok disconnects, demo breaks.
- **Option C:** Fly.io or Google Cloud Run. More setup but more stable. Only if your team has existing accounts.

**CRITICAL:** Whatever host you choose, test the endpoint externally (from a phone hotspot, not the same network) before registering it on Agentverse.

---

## 5. OmegaClaw Skill Definition

This is the integration layer that tells OmegaClaw about your agent. Without this, OmegaClaw cannot discover or invoke your Agentverse agent, and the prize track requirement is not met.

### 5.1 Skill Config

OmegaClaw skills are defined as structured configs. The exact format depends on the OmegaClaw version at the hackathon — get the template from the Fetch.ai team on day 1. The conceptual structure:

```json
{
  "skill_name": "identify_person",
  "description": "Identify a person from their name badge and return professional context.",
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
    "summary": "string"
  },
  "timeout_ms": 5000
}
```

### 5.2 OmegaClaw Integration with OpenClawBridge.swift

The existing OpenClawBridge.swift in the VisionClaw repo POSTs to `/v1/chat/completions`. OmegaClaw sits between the Swift app and your Agentverse agent. The bridge config in Secrets.swift:

```swift
static let openClawHost = "https://YOUR_OMEGACLAW_ENDPOINT"
static let openClawPort = 443
static let openClawGatewayToken = "YOUR_OMEGACLAW_TOKEN"
```

Verify on day 1: does OmegaClaw expose `/v1/chat/completions`? If it uses a different path, update OpenClawBridge.swift. One function change, 10 minutes.

---

## 6. iOS App Changes from VisionClaw Baseline

The VisionClaw repo is the base. Minimize changes. Every line you write that already exists in the repo is wasted time.

### 6.1 Changes Required

| File | Change | Complexity | Owner |
|------|--------|-----------|-------|
| Secrets.swift | Fill in Gemini API key, OmegaClaw host/port/token | Trivial | A |
| GeminiConfig.swift | New system prompt (see Section 7), add identify_person tool declaration | Low | B |
| ToolCallModels.swift | Add identify_person function declaration schema | Low | C |
| OpenClawBridge.swift | Update endpoint path/auth if OmegaClaw format differs | Low-Med | C |
| Nothing else | Do not touch GeminiLiveService, AudioManager, IPhoneCameraManager, WebRTC | N/A | All |

### 6.2 identify_person Tool Declaration (ToolCallModels.swift)

```json
{
  "name": "identify_person",
  "description": "Identify a person visible in the camera frame from their name badge. Use when the user asks who someone is, who they are looking at, or to identify a person.",
  "parameters": {
    "type": "OBJECT",
    "properties": {
      "name": {
        "type": "STRING",
        "description": "Full name extracted from the badge"
      },
      "organization": {
        "type": "STRING",
        "description": "Company or organization on the badge"
      },
      "title": {
        "type": "STRING",
        "description": "Job title on the badge, or empty string if not visible"
      }
    },
    "required": ["name", "organization"]
  }
}
```

---

## 7. Gemini System Prompt (GeminiConfig.swift)

This controls everything Gemini does. Get this right before hour 3. Iterate based on testing.

```
You are ContextLens, a hands-free AI assistant running on Meta Ray-Ban smart glasses.
The user cannot look at a screen. All output is spoken audio only.

YOUR PRIMARY FUNCTION:
When the user asks 'Who is this?', 'Who am I looking at?', or similar,
look at the current camera frame, read the name badge, and call identify_person
with the name, organization, and title you can see.

VISION RULES:
- Always check the camera frame before responding to identity questions.
- Extract name and organization from any visible badge, lanyard, or name tag.
- If you cannot read the badge clearly, say 'I cannot read the badge, try moving closer'
  and DO NOT call identify_person.
- If there is no badge visible, say 'I do not see a name badge in view.'

RESPONSE RULES:
- Maximum 2 sentences. Lead with the person's name.
- Speak naturally, not like a database readout.
- Never say 'According to my search' or 'Based on available information'.
- If confidence is low, add: 'though I am not fully certain about the details.'
- Never repeat the badge text back verbatim. Add context, not transcription.

TOOL USE:
- Always verbally acknowledge before tool calls: 'Looking that up.'
- Never speak the result before receiving the tool response.
- If the tool fails, say 'I could not find information on that person right now.'
```

---

## 8. Phased Delivery Plan

| Phase | Hours | Goal | Gate |
|-------|-------|------|------|
| 0: Foundation | 0-2 | Repo cloned, Secrets.swift filled, app runs on iPhone, Gemini audio confirmed working | Say 'Hello' — Gemini responds via glasses speaker |
| 1: Agent Build | 2-6 | Python uAgent built, FastAPI running locally, Gemini context lookup confirmed working, Agentverse registration complete | curl to your FastAPI returns a valid person summary |
| 2: OmegaClaw Skill | 6-10 | OmegaClaw skill definition registered, end-to-end test: iOS app → OmegaClaw → Agentverse agent → spoken response | Say 'Who is this?' at a badge — spoken context returned |
| 3: Glasses Hardware | 10-16 | Swap from iPhone camera to Meta Glasses. All Phase 2 functionality working through glasses. | Full demo flow works through glasses hardware |
| 4: Polish & Demo Prep | 16-20 | 3 scripted scenarios rehearsed, error handling tested, README + pitch written | 3-minute dry run passes without intervention |

### 8.1 Phase 0 Checklist (Hours 0-2)

- `git clone https://github.com/Intent-Lab/VisionClaw.git`
- `cd samples/CameraAccess && open CameraAccess.xcodeproj`
- `cp CameraAccess/Secrets.swift.example CameraAccess/Secrets.swift`
- Add Gemini API key to Secrets.swift
- Build + run on physical iPhone (not simulator — audio requires real device)
- Tap 'Start on iPhone', tap AI button, say 'Hello' — confirm spoken response
- Confirm OmegaClaw endpoint format with Fetch.ai team (get exact URL + auth token)

### 8.2 Phase 1 Checklist (Hours 2-6) — Engineer C/D

- `mkdir contextlens-agent && cd contextlens-agent`
- `pip install uagents fastapi uvicorn google-generativeai python-dotenv`
- Write agent.py, context_service.py, models.py, main.py (see Section 4.2)
- Test context_service.py standalone: `python -c "import asyncio; from context_service import get_person_context; print(asyncio.run(get_person_context('Elon Musk', 'xAI', 'CEO')))"`
- Run FastAPI locally: `uvicorn main:app --port 8001`
- Test endpoint: `curl -X POST http://localhost:8001/v1/chat/completions -H 'Content-Type: application/json' -d '{"messages":[{"role":"user","content":"Identify person: Elon Musk, xAI, CEO"}]}'`
- Deploy to Railway/Render — get public HTTPS URL
- Test deployed endpoint from phone hotspot (not same network)
- Register agent on Agentverse — note agent address
- Screenshot the registered agent on Agentverse for demo/judging evidence

### 8.3 Phase 2 Checklist (Hours 6-10) — Engineer C + A

- Get OmegaClaw skill config template from Fetch.ai team
- Fill in skill config with agent address and trigger phrases
- Register skill in OmegaClaw
- Update Secrets.swift with OmegaClaw host + token
- Update OpenClawBridge.swift if endpoint format differs
- Add identify_person tool declaration to GeminiConfig.swift
- Update system prompt in GeminiConfig.swift (see Section 7)
- End-to-end test on iPhone: point camera at printed name badge, say 'Who is this?'
- Confirm spoken response within 8 seconds
- Test failure case: point at blank wall, confirm graceful response

### 8.4 Phase 3 Checklist (Hours 10-16) — Engineer A

- Enable Developer Mode in Meta AI app: Settings > App Info > tap version 5x
- In app: tap 'Start Streaming', connect glasses
- Confirm camera switches to glasses PoV
- Confirm mic/speaker routing: voice from glasses, audio from phone speaker
- Run full identify_person flow through glasses
- Test audio session switch to .videoChat (no echo/feedback)
- Walk around hackathon floor and test on real badges (with permission)

### 8.5 Phase 4 Checklist (Hours 16-20) — All

- Run demo script 5 times without stopping
- Test circuit breaker: kill FastAPI, confirm Gemini speaks fallback after 3 failures
- Prepare 3 printed name badge props as backup if real badges not available
- Write README with setup instructions and Agentverse agent address
- Prepare judging evidence: screenshots of Agentverse registration, skill config, demo video

---

## 9. Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| OmegaClaw skill registration format unknown / not documented | Critical | First task day 1: find a Fetch.ai team member and get the exact skill config format and a working example. Do not guess. This is required for the prize track. |
| Agentverse agent not reachable from OmegaClaw (firewall / network) | Critical | Deploy to Railway/Render immediately. Test from external network. ngrok is a last resort only — it disconnects. |
| Gemini cannot read the badge from glasses camera resolution | High | Test badge readability in Phase 2 with printed badges at varying distances. If glasses resolution is insufficient, have the user move to 30-50cm from the badge. Add to system prompt: 'If badge is not readable, ask user to move closer.' |
| OmegaClaw endpoint format differs from /v1/chat/completions | High | Confirm format in Phase 0. One function change in OpenClawBridge.swift. 10 minutes. |
| Person not findable by Gemini (private individual, no web presence) | Medium | Confidence field handles this. System prompt instructs Gemini to say 'I found [Name] from [Org] but could not find further details.' Demo with well-known public figures as backup. |
| uAgents SDK breaking change / version incompatibility | Medium | Pin all versions in requirements.txt. Test install on a clean virtualenv before hackathon. |
| Meta Glasses not pairing or DAT SDK issues | Medium | Phase 1-2 fully works on iPhone camera. Demo can run on iPhone if glasses fail. Never let glasses block agent work. |
| OmegaClaw latency stack adds >5s on top of agent time | Medium | Measure end-to-end in Phase 2. If latency >8s, add optimistic Gemini speech ('Looking that up, one moment') to cover the wait. |

---

## 10. Demo Script — 3-Minute Hackathon Pitch

Prepare 3 printed name badge props. Do not rely on real badges being available or readable. Control your demo.

| # | Scene | Duration | User Says | Expected Output | Fallback |
|---|-------|----------|-----------|-----------------|----------|
| 1 | Setup | 20s | (Narrator) 'You're at a conference. You see someone interesting but don't want to pull out your phone.' | N/A — context setting | N/A |
| 2 | Vision check | 20s | 'What do I see?' (pointing at badge) | Gemini describes the badge / scene | Skip if glasses unavailable, use iPhone |
| 3 | Primary demo | 60s | 'Who is this?' (pointing at printed badge: 'Sarah Chen, CTO, Fetch.ai') | Gemini reads badge, calls identify_person, speaks: 'That's Sarah Chen, CTO at Fetch.ai. She leads the Agentverse platform and agent economy infrastructure.' | Have result pre-cached as fallback audio |
| 4 | Second badge | 40s | 'Who is this?' (different badge: 'Alex Kumar, Founder, Ritual') | Second identify_person call, different context spoken back | Skip if time tight |
| 5 | Failure handling | 20s | 'Who is this?' (pointing at blank wall) | Gemini: 'I do not see a name badge in view.' | N/A — this IS the fallback demo |
| 6 | Wrap | 20s | (Narrator) Architecture explanation: Agentverse agent + OmegaClaw skill + Meta glasses | Show Agentverse dashboard on laptop with agent registered | Show screenshot if dashboard slow |

Rehearse minimum 5 full runs. Know what Gemini says when the badge is unreadable. Know what happens when OmegaClaw times out. Every failure mode should be something you can explain as a feature, not an apology.

---

## 11. Engineer Assignments

| Engineer | Primary Role | Phase 0-2 | Phase 3-4 |
|----------|-------------|-----------|-----------|
| A | iOS App + Glasses Hardware | Clone repo, Secrets.swift, Gemini audio pipeline stable on iPhone, Phase 3 glasses integration | Glasses hardware testing, audio session validation, demo rehearsal |
| B | Gemini Config + System Prompt | Write + iterate system prompt, identify_person tool declaration, vision OCR testing with printed badges at range | Latency tuning, system prompt edge case testing, backup for any Gemini API issues |
| C | Agentverse Agent + OmegaClaw Skill | Python uAgent, FastAPI service, Agentverse registration, OmegaClaw skill config, OpenClawBridge.swift update | End-to-end integration testing, circuit breaker testing, agent monitoring during demo |
| D | Agent Context Service + QA | context_service.py Gemini API implementation, deployment to Railway/Render, external endpoint testing, test with 10+ different person queries | README writing, judging evidence preparation, demo script practice, fallback scenario docs |

---

## 12. Latency Budget

| Step | Target | Notes |
|------|--------|-------|
| Voice to Gemini STT | <500ms | Gemini Live native audio — no separate STT step |
| Gemini badge OCR + tool call decision | <1s | Vision + intent classification happens in same Gemini inference |
| Gemini verbal acknowledgment ('Looking that up') | <500ms | Spoken before tool call dispatched — covers wait time |
| OmegaClaw routing to Agentverse agent | <1s | Network hop: OmegaClaw → Agentverse → FastAPI |
| Gemini API call inside context_service.py | <2s | gemini-1.5-flash is fast for this prompt length |
| Agent response back to OmegaClaw → iOS | <500ms | Return trip |
| Gemini synthesis to audio | <1s | PCM audio generation |
| **Total end-to-end** | **<7s** | Acceptable for hackathon demo. Verbal ack covers first 2s. |

---

## 13. Out of Scope

- Separate orchestration model (Claude, GPT-4o) — Gemini Live handles this natively
- Gemma sub-agents — no benefit, added latency and complexity
- Persistent memory across sessions
- Multi-language support
- Android build
- WebRTC live streaming — cannot run simultaneously with Gemini Live
- Always-on passive identification — privacy concern and battery/latency constraint
- Facial recognition — use badge text OCR only, not biometric identification
- Any other OmegaClaw tool (web search, calendar, shopping) — single focused skill wins over breadth

---

## 14. Appendix — Key Links & Commands

### 14.1 Links

- VisionClaw repo: https://github.com/Intent-Lab/VisionClaw
- Agentverse: https://agentverse.ai
- uAgents SDK docs: https://docs.fetch.ai/uagents
- Fetch.ai OmegaClaw docs: https://fetch.ai/docs
- Gemini API key: https://aistudio.google.com/apikey
- Gemini Live API: https://ai.google.dev/gemini-api/docs/live
- Meta DAT SDK: https://developers.facebook.com/docs/ray-ban-meta-smart-glasses
- Railway deployment: https://railway.app

### 14.2 Key Commands

```bash
# iOS App Setup
git clone https://github.com/Intent-Lab/VisionClaw.git
cd VisionClaw/samples/CameraAccess
cp CameraAccess/Secrets.swift.example CameraAccess/Secrets.swift
open CameraAccess.xcodeproj

# Python Agent Setup
mkdir contextlens-agent && cd contextlens-agent
python -m venv venv && source venv/bin/activate
pip install uagents fastapi uvicorn google-generativeai python-dotenv

# Run agent locally
python agent.py            # uAgent (port 8001)
uvicorn main:app --port 8001  # FastAPI (same port, choose one entry point)

# Test context service
python -c "
import asyncio
from context_service import get_person_context
print(asyncio.run(get_person_context('Sarah Chen', 'Fetch.ai', 'CTO')))
"

# Test FastAPI endpoint
curl -X POST http://localhost:8001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Identify person: Sarah Chen, Fetch.ai, CTO"}]}'

# Deploy to Railway
npm install -g @railway/cli
railway login && railway init && railway up
```

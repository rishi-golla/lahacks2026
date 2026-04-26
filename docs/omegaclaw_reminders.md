# OmegaClaw reminders: in-core vs backend

## What stock OmegaClaw can do

- **Memory + time in context:** The loop includes `TIME:` in context (`src/loop.metta`). The model can `remember` a note and later reason about it when the user returns or on a **wake** cycle.
- **Wake cycles:** When idle, `wakeupInterval` (default ~10 minutes) can grant extra turns (`maxWakeLoops`) so the agent may do self-initiated work. Whether it “reminds” you is **LLM-dependent**, not a guaranteed alarm.
- **No OS alarm API:** There is no first-class “fire at 3:00pm wall clock” skill in the default `getSkills` list.

## Reliable reminders (recommended for glasses / mobile)

Implement **outside** the MeTTa loop:

1. **Backend or device scheduler** (cron, `asyncio` timer, iOS local notification) at the requested time.
2. Optionally **inject** a new synthetic task into the same HTTP bridge queue (`LAHACKS_TASK_JSON:` line) so OmegaClaw can phrase the reminder or use `send` when the user is in session.

## Summary

| Approach | Precision | Depends on |
|----------|-----------|------------|
| In-core wake + `remember` | Low / fuzzy | Model + wake interval |
| Backend timer + synthetic inbound | High | Your FastAPI / client scheduler |

See also [OMEGACLAW_DOCKER_WORKFLOW.md](OMEGACLAW_DOCKER_WORKFLOW.md) and the LA Hacks instructions doc.

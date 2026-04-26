# Agentverse Skill Registration Notes

These JSON files are the repo-side metadata for the Agentverse specialists used by OmegaClaw.

## New specialist agents

- `people_search_agent.json`
- `mail_sending_agent.json`
- `task_scheduling_agent.json`
- `reminder_agent.json`
- `purchase_agent.json`

## Existing specialists

- `identify_person.json`
- `describe_scene.json`
- `google_search.json`
- `google_calendar.json`
- `gmail.json`

## Agentverse launch checklist

1. Create a new agent on `https://agentverse.ai/agents/launch/choose`
2. Use the same skill name as the JSON filename
3. Copy the deployed agent address (`agent1q...`)
4. Replace the placeholder `agent_address` in the matching JSON file
5. Repeat for each specialist you want OmegaClaw to call remotely

## Suggested launch order

1. `mail_sending_agent`
2. `task_scheduling_agent`
3. `reminder_agent`
4. `people_search_agent`
5. `purchase_agent`

That order keeps the demo-focused Google workflow agents first and leaves the broader research / commerce agents for last.

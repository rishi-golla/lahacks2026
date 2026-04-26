"""Registration script for the Agentverse mail_sending_agent.

Paste the Agentverse-generated registration code into this file and run it
from a terminal where AGENTVERSE_KEY and AGENT_SEED_PHRASE are already set.
"""
import os
from uagents_core.utils.registration import (
    register_chat_agent,
    RegistrationRequestCredentials,
)

register_chat_agent(
    "mail_sending_agent",
    "https://moisture-lively-uncombed.ngrok-free.dev",
    active=True,
    credentials=RegistrationRequestCredentials(
        agentverse_api_key=os.environ["AGENTVERSE_KEY"],
        agent_seed_phrase=os.environ["AGENT_SEED_PHRASE"],        
    ),
)
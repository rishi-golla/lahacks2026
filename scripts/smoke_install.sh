#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/../contextlens-agent"
python -m venv /tmp/contextlens_smoke_venv
/tmp/contextlens_smoke_venv/bin/pip install -q -r requirements.txt
/tmp/contextlens_smoke_venv/bin/python -c "
from context_service import get_person_context
from describe_service import get_scene_description
from models import PersonQuery, PersonContext
print('imports ok')
"
echo "smoke test passed"

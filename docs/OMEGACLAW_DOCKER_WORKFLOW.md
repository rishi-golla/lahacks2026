# OmegaClaw Docker workflow (LA Hacks track)

This doc mirrors **§0.1** of the integration plan (clone → optional stock image → edit source → build → run). It does **not** replace the official [OmegaClaw Instructions](_LAHacks2026%20-%20OmegaClaw%20Instructions.md).

## Phase A — Clone and branch

1. `git clone https://github.com/trueagi-io/PeTTa && cd PeTTa && mkdir -p repos`
2. `git clone https://github.com/asi-alliance/OmegaClaw-Core.git repos/OmegaClaw-Core && cd repos/OmegaClaw-Core`
3. `git fetch origin hackathon-2604 && git checkout hackathon-2604`

For this monorepo, the same tree may already exist at `PeTTa/repos/OmegaClaw-Core` (include your channel patches there before building).

## Phase B — Optional stock image

Verify Docker and keys without local patches:

```bash
docker pull singularitynet/omegaclaw:hackathon2604
curl -fsSL https://raw.githubusercontent.com/asi-alliance/OmegaClaw-Core/refs/tags/hackathon2604/scripts/omegaclaw | bash -s -- singularitynet/omegaclaw:hackathon2604
```

## Phase C — Custom code (before your image build)

Implement HTTP bridge channel and `channels.metta` wiring under `repos/OmegaClaw-Core`, then rebuild.

## Phase D — Build your image

From `repos/OmegaClaw-Core`:

```bash
docker build -t my-omegaclaw:dev .
```

Rebuild after any change under that directory.

## Phase E — Run with LA Hacks channel

From `repos/OmegaClaw-Core`:

```bash
./scripts/omegaclaw my-omegaclaw:dev
```

Choose **option 3** (HTTP bridge) when prompted so the container long-polls this backend’s `/internal/omegaclaw/next`.

Start the FastAPI backend first (see [omegaclaw_backend_channel_runbook.md](omegaclaw_backend_channel_runbook.md)) with `OMEGACLAW_BRIDGE_ENABLED=1` and published port **8000**.

On **Linux**, add Docker host mapping so the container can reach the host API, e.g.:

`--add-host=host.docker.internal:host-gateway`

The `scripts/omegaclaw` wrapper adds this automatically when `commchannel=lahacks_http`.

## Backend process

Run the FastAPI app on the host (or any container you maintain) so OmegaClaw can reach `LAHACKS_BRIDGE_BASE_URL`, for example:

`cd backend && OMEGACLAW_BRIDGE_ENABLED=1 uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`

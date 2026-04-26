# Edith

Edith is the live site for the shared-glasses workflow.

## What it does

- lets a user connect their Google account
- shows which user is currently action-enabled for the shared glasses
- displays the Google action history produced by glasses-triggered tasks

## Local development

```bash
cd apps/edith
npm install
npm run dev
```

By default, the frontend expects the backend at `http://127.0.0.1:8000`.

To override that:

```bash
set VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Shared glasses behavior

- Anyone can use the glasses for general assistant tasks.
- Google actions stay locked until someone connects on the site.
- When a protected action is requested, the glasses ask:
  `Before I continue, just to confirm, are you <name>?`
- Saying `yes` allows the action to continue.

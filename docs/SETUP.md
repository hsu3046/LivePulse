# LivePulse Setup

## Requirements

- Python 3.13 recommended
- PostgreSQL client (`psql`) for applying and verifying migrations
- A Supabase project for production persistence

## Local environment

Create `.env.local` from `.env.example` and keep it outside Git.

| Variable | Purpose |
|---|---|
| `SUPABASE_URL` | Supabase project API URL |
| `SUPABASE_PUBLISHABLE_KEY` | Browser-safe Realtime/API key |
| `DATABASE_URL` | Transaction Pooler URL on port 6543 |
| `DIRECT_URL` | Session Pooler or direct URL on port 5432 |
| `PUBLIC_BASE_URL` | QR-code origin |
| `LIVEPULSE_DB` | SQLite fallback path |

Start with Supabase enabled:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --env-file .env.local --host 0.0.0.0 --port 8000
```

Start in SQLite fallback mode by leaving `DATABASE_URL` empty.

## Database migrations

Apply the SQL files in filename order from `supabase/migrations/` using `DIRECT_URL`.
Application startup verifies that `"LivePulse_events"` exists but does not run DDL
during a serverless cold start.

## Verification

```bash
source .venv/bin/activate
pytest -q
```

The automated suite uses a temporary SQLite database. A separate Supabase smoke test
should create a uniquely named event, exercise the full flow, and delete the event in a
`finally` cleanup block.

## Retention

Automatic retention cleanup is not enabled yet. Records remain in Supabase until they
are explicitly deleted. Before production use, add a scheduled cleanup for ended events
older than the agreed retention window (currently planned as 30 days), and verify that
CSV export is completed before deletion.

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

## Vercel production

The production project is `team-aib/livepulse` and the stable URL is
<https://livepulse-tau.vercel.app>.

- Keep the Vercel Framework Preset set to `FastAPI`.
- `pyproject.toml` declares `app.main:app` as the entrypoint.
- Set only `DATABASE_URL` for the Production runtime. Do not expose `DIRECT_URL`.
- Keep the function region at `hnd1`, next to the Supabase `ap-northeast-1` database.
- Git deployments build the current GitHub default branch.

If a deployment reports `Ready` but every path returns Vercel `NOT_FOUND`, inspect the
build list. A build containing only `.` and no lambda means the project was treated as
static content, usually because its Framework Preset is `Other`.

## Retention

Automatic retention cleanup is not enabled yet. Records remain in Supabase until they
are explicitly deleted. Before production use, add a scheduled cleanup for ended events
older than the agreed retention window (currently planned as 30 days), and verify that
CSV export is completed before deletion.

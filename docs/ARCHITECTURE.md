# LivePulse Architecture

## Overview

LivePulse is a FastAPI application with static browser clients for hosts, participants,
and presentation displays.

```text
Browser clients
  ├─ HTTP API ─────── Vercel FastAPI (hnd1) ─────── Supabase PostgreSQL
  └─ WebSocket ────── Vercel FastAPI ────────────── in-process ConnectionManager
```

Supabase PostgreSQL is the production source of truth. SQLite remains available only
as a local fallback and as the isolated database used by automated tests.

Vercel packages the application as one Python Function. `pyproject.toml` explicitly
selects `app.main:app`, limits setuptools discovery to the `app` package, and includes
the browser files under `app/static`.

## Persistence selection

- `DATABASE_URL` present: PostgreSQL through the Supabase Transaction Pooler.
- `DATABASE_URL` absent: SQLite at `LIVEPULSE_DB`.
- `DIRECT_URL`: migrations and administrative verification only.

PostgreSQL prepared statements are disabled because Supavisor Transaction Pooler mode
does not support them.

## Tables

PostgreSQL identifiers are quoted to preserve the required case-sensitive prefix.

- `"LivePulse_events"`
- `"LivePulse_questions"`
- `"LivePulse_options"`
- `"LivePulse_participant_sessions"`
- `"LivePulse_responses"`
- `"LivePulse_event_logs"`

All six tables have Row Level Security enabled and grant no direct access to `anon` or
`authenticated`. Browser writes continue to pass through the FastAPI domain layer.

The shared Supabase `public` schema already contains an unrelated unprefixed `events`
table with a different model. It is intentionally preserved. LivePulse code and
migrations must never read, rename, or delete that table.

## Transactions and concurrency

PostgreSQL state transitions lock the event row before question rows. Response
submissions acquire shared locks while close/reveal operations acquire update locks.
This prevents a response from being committed after a question has closed and ensures
only one question can be open for an event.

Question positions use a deferred unique constraint so an entire reorder can complete
inside one transaction without transient uniqueness conflicts.

## Realtime limitation

The current `ConnectionManager` stores WebSocket clients in process memory. It works
for a single local process but cannot coordinate separate Vercel Function instances.
Supabase Realtime Broadcast is the planned shared invalidation layer. Until that work
is complete, production deployment must not assume exact multi-instance presence or
broadcast delivery.

# LivePulse Memory

## 2026-07-24 — Supabase PostgreSQL persistence

- Selected Supabase PostgreSQL as the production source of truth, with SQLite retained
  for local fallback and automated tests.
- Created six quoted, case-sensitive `LivePulse_` tables with constraints, indexes,
  RLS, and no direct `anon`/`authenticated` grants.
- Confirmed that the existing unprefixed `public.events` table belongs to another
  workload; it was preserved and must remain outside LivePulse migrations.
- Runtime connects through `DATABASE_URL` (Transaction Pooler); migrations use
  `DIRECT_URL`.
- Copied existing SQLite data nondestructively: 1 event, 1 question, 6 options,
  0 participant sessions, 0 responses, and 2 event logs.
- Added PostgreSQL row locking, timestamp serialization, migration docs, and tests.
- Verification completed: 15 automated tests, Python compilation, a full real
  PostgreSQL event flow with cleanup, and a Supabase-backed HTTP/QR smoke test.
- Deferred: multi-instance Supabase Realtime, Vercel deployment, and automatic
  30-day retention cleanup.

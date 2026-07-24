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
- Deployed Vercel project `team-aib/livepulse` to
  `https://livepulse-tau.vercel.app` with the FastAPI preset and `hnd1` function
  region. Production HTTP, Supabase reads, QR generation, and WebSocket snapshots
  passed.
- Vercel build requirements: explicit `app.main:app` entrypoint and setuptools
  discovery restricted to `app*`; otherwise the project becomes static or
  `supabase/` is mistaken for another Python package.
- Deferred: multi-instance Supabase Realtime and automatic 30-day retention cleanup.

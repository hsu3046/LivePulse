# LivePulse Project Memory

## Current persistence baseline

- Supabase PostgreSQL is the production source of truth.
- SQLite is retained for local fallback and automated tests.
- Every application-owned PostgreSQL table uses the exact quoted `LivePulse_` prefix.
- FastAPI owns all public database access; browser clients do not receive database
  credentials.
- The pre-existing unprefixed `public.events` table belongs to another workload and
  must remain untouched.

## Verified on 2026-07-24

- Supabase migrations and RLS were applied.
- Existing SQLite data was copied without deleting the source.
- The full event lifecycle, CSV export, WebSocket snapshot, server startup, host page,
  API response, and QR generation were verified against Supabase.
- Vercel production was deployed to `https://livepulse-tau.vercel.app` in `hnd1`.
  Production host HTML, Supabase reads, QR PNG generation, and a WebSocket host
  snapshot all passed.
- The automated suite passed all 15 tests.

## Deferred

- Supabase Realtime for multi-instance broadcasting
- Automatic deletion of ended events after the planned 30-day retention window
- Upstash only if load testing later justifies shared presence, rate limiting,
  counters, or Pub/Sub

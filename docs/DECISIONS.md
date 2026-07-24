# LivePulse Decisions

## 2026-07-24 — Supabase PostgreSQL is the production source of truth

### Decision

Use Supabase PostgreSQL for event, question, participant session, response, and audit
data. Keep SQLite as a local and automated-test fallback.

### Why

- Event responses must survive process restarts and Vercel instance replacement.
- SQL constraints and transactions match answer replacement, result aggregation, and
  CSV export better than a Redis-only data model.
- A single source of truth avoids dual-write divergence.

### Consequences

- Runtime requires `psycopg[binary]`.
- Migrations are explicit and are not executed on every application startup.
- Upstash is deferred until load tests show a need for shared counters, presence,
  rate limiting, or Pub/Sub.

## 2026-07-24 — Exact `LivePulse_` table prefix

All application-owned PostgreSQL tables use a quoted, case-sensitive `"LivePulse_"`
prefix. SQL must always reference those physical names through the database adapter or
quote them explicitly in migration files.

The Supabase project also contains an unrelated `public.events` table. Its fields and
records belong to another workload and must remain untouched; the prefix is the
namespace boundary that prevents collisions.

## 2026-07-24 — RLS deny-by-default

All application tables enable Row Level Security and revoke direct access from
`anon` and `authenticated`. The public browser never receives the database password.
FastAPI remains the trusted write boundary.

## 2026-07-24 — Retention is explicit, not implied by persistence

Supabase stores event records until an explicit deletion job runs. The planned
production policy is to let organizers export CSV after an event and automatically
delete ended events after 30 days. That scheduler is not part of the current migration,
so deployment must not claim automatic expiry yet.

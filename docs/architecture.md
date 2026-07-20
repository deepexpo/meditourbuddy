# Architecture

## Components

```
meditourbuddy/
  packages/
    shared/                  # Drizzle schema, db client, FX table, seed pipeline
      src/schema.ts           # 6 tables, 5 pg enums, Drizzle relations
      src/db.ts               # postgres-js client + drizzle() instance (reads DATABASE_URL)
      src/fx.ts                # static currency->USD table used for price normalization
      src/seed/                # idempotent seed script + zod validation for seed/clinics.yaml
      seed/clinics.yaml        # 14 real, researched clinics (sources cited inline)
    clinic-registry-mcp/      # the MCP server (portfolio centerpiece)
      src/tools/                # one handler function per MCP tool
      src/server.ts             # registers all 5 tools on an McpServer
      src/index.ts              # entrypoint: connects StdioServerTransport
    agent/                    # phase 2 — orchestrator CLI, not built yet
  docker-compose.yml         # local Postgres for tests (not Supabase)
  docs/
    spec.md                   # original spec: data model, tool contracts, build order
    architecture.md           # this file
```

## Data flow

1. **Seeding**: `packages/shared/seed/clinics.yaml` is parsed and validated against a Zod schema
   (`src/seed/types.ts`) that mirrors the Drizzle enums exactly, so bad seed data fails fast
   instead of hitting a Postgres constraint. `src/seed/run.ts` upserts the 12 reference
   `procedures` rows, then for each clinic: upserts the `clinics` row by `slug`, then
   delete-and-reinserts its `accreditations` / `practitioners` / `clinic_procedures` rows inside a
   transaction. This makes the whole script safely re-runnable.

2. **Serving**: `clinic-registry-mcp`'s tool handlers query the same `db`/schema exported from
   `@meditourbuddy/shared` — some via the Drizzle query builder (dynamic filters, e.g.
   `search_clinics`), one via the relational query API (`get_clinic_profile`, which needs a
   single clinic plus three nested collections in one shot).

3. **Transport**: the server is registered on an `McpServer`
   (`@modelcontextprotocol/sdk/server/mcp.js`, v1.x — the stable line; the SDK's `main` branch is
   a v2 beta not stabilizing until July 28, 2026) and connected over `StdioServerTransport`. Claude
   Desktop spawns the server as a child process and talks JSON-RPC over stdin/stdout — no HTTP
   server, no port, no auth to configure for local use.

## Design decisions worth knowing

- **Currency normalization is a static table, not a live FX API** (`packages/shared/src/fx.ts`):
  every price-bearing tool output is USD-normalized deterministically, which matters for the
  Vitest suite (no network flakiness) and for the demo (no dependency on a third-party FX service
  being up). The table has an explicit `as_of` date; refresh it manually when it goes stale.
- **Accreditation strength ranking** (used to sort `search_clinics` results): `JCI > GHA > AACI >
  ISO_9001 > NATIONAL`, matching `accreditationBodyEnum`'s declared order in `schema.ts`. There's
  no universally "correct" ordering across these bodies — this is a reasonable default, not a
  claim about real-world prestige.
- **The disclaimer and `stale` flag are additive**, not part of the literal shapes documented in
  `docs/spec.md`'s tool-by-tool section — the spec's Guardrails section requires them on every
  response, so they're layered on top of each tool's documented output as extra top-level fields
  rather than replacing anything.
- **Clinics can have zero accreditations.** Several real clinics in the seed data do — the
  research repeatedly turned up clinics whose only "credentials" were unverifiable marketing claims
  (US professional-association membership, generic "ADA accredited" language with no registry
  link). Rather than force a `NATIONAL` row onto those, they're seeded with `accreditations: []`.
  `search_clinics`' `require_accreditation` guardrail (default `true`) filters them out of normal
  results automatically — this is that guardrail doing its job, not a data gap to paper over.

## Recording the demo GIF

This isn't something that can be generated headlessly — it's a real Claude Desktop session. Once
the server is connected (see the README's "Connecting to Claude Desktop" section):

1. Open Claude Desktop, start a new chat.
2. Ask something like *"Find me an accredited all-on-4 clinic in Istanbul under $8K"* — this is
   the spec's literal demo query and is known to return a real result (Maltepe Dental Clinic,
   ISO_9001, ~$3,200 USD-equivalent).
3. Let Claude call `search_clinics` and show the result; optionally follow up with
   `get_clinic_profile` or `verify_accreditation` on the returned clinic to show the evidence
   chain.
4. Screen-record it (macOS: Cmd+Shift+5, or a tool like [Kap](https://getkap.co/)) and trim/export
   as a GIF around 30 seconds.
5. Drop it in the repo (e.g. `docs/demo.gif`) and replace the placeholder in the README's Demo
   section with `![demo](docs/demo.gif)`.

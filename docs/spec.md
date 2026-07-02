# MediTourBuddy — Clinic Registry MCP Spec (v0.1)

Portfolio-first MVP. Dental vertical, Canada-outbound, destinations: Turkey (Istanbul) and Mexico (Los Algodones, Cancún).

## Repo structure

```
meditourbuddy/
  packages/
    clinic-registry-mcp/     # MCP server (portfolio centerpiece)
    agent/                   # orchestrator CLI (phase 2)
    shared/                  # Drizzle schema, shared types
  docs/
    architecture.md
    spec.md                  # this file
```

Tooling: pnpm workspaces, TypeScript 5.x, Node 20, Vitest, Drizzle ORM, Supabase Postgres.

---

## Data model

### clinics
| column | type | notes |
|---|---|---|
| id | uuid PK | `gen_random_uuid()` |
| slug | text unique | e.g. `dentgroup-istanbul` |
| name | text | |
| country | text | ISO-3166 alpha-2: `TR`, `MX` |
| city | text | |
| address | text | |
| latitude / longitude | numeric | for map display later |
| languages | text[] | e.g. `{en,tr}` |
| year_established | int nullable | |
| website | text nullable | |
| verified_at | timestamptz nullable | when WE last verified this clinic |
| created_at / updated_at | timestamptz | |

### accreditations
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| clinic_id | uuid FK → clinics | |
| body | enum | `JCI`, `GHA`, `AACI`, `ISO_9001`, `NATIONAL` |
| reference_id | text nullable | accreditor's registry ID |
| valid_from / valid_until | date nullable | |
| source_url | text | link to the accreditor's public registry entry — this is the verifiability story |

### practitioners
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| clinic_id | uuid FK | |
| full_name | text | |
| title | text | e.g. "Prosthodontist" |
| license_number | text nullable | |
| license_country | text | |
| years_experience | int nullable | |
| profile_url | text nullable | |

### procedures
Reference table, seeded. ~12 rows for dental v1.

| column | type | notes |
|---|---|---|
| id | uuid PK | |
| code | text unique | `IMPLANT_SINGLE`, `IMPLANT_ALL_ON_4`, `CROWN_ZIRCONIA`, `VENEER_EMAX`, `ROOT_CANAL`, `FULL_MOUTH_RECON`, etc. |
| name | text | |
| category | enum | `implant`, `restorative`, `cosmetic`, `surgical` |
| typical_visits | int | implants = 2 (3–6 months apart) — itinerary logic depends on this |
| recovery_days_onsite | int | days patient must stay near clinic post-procedure |

### clinic_procedures (pricing)
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| clinic_id | uuid FK | |
| procedure_id | uuid FK | |
| price_min / price_max | numeric | |
| currency | text | `USD`, `EUR`, `CAD`, `MXN`, `TRY` |
| includes | text[] | e.g. `{consultation,xray,hotel_transfer}` |
| last_verified | date | pricing goes stale fast — surface this in results |

### reviews_summary (optional, phase 2)
Aggregated only — no scraping individual reviews. `clinic_id`, `source` (`google`, `whatclinic`), `rating`, `review_count`, `fetched_at`.

---

## MCP tools

All inputs validated with Zod. All outputs JSON.

### 1. `search_clinics`
Find vetted clinics matching a case.
```ts
input: {
  procedure_code: string,          // e.g. "IMPLANT_ALL_ON_4"
  country?: "TR" | "MX",
  max_budget_usd?: number,
  language?: string,               // default "en"
  require_accreditation?: boolean  // default true
}
output: {
  clinics: Array<{
    slug, name, city, country,
    accreditations: string[],      // ["JCI", "NATIONAL"]
    price_range_usd: { min, max } | null,
    practitioner_count: number,
    verified_at: string | null
  }>
}
```
Rules: never return clinics with zero accreditations when `require_accreditation` is true. Sort by (accreditation strength, then price). Max 10 results.

### 2. `get_clinic_profile`
Full detail for one clinic.
```ts
input: { slug: string }
output: {
  clinic: {...all clinic fields},
  accreditations: [{ body, reference_id, valid_until, source_url }],
  practitioners: [{ full_name, title, years_experience }],
  procedures: [{ code, name, price_min, price_max, currency, includes, last_verified }]
}
```

### 3. `verify_accreditation`
The trust tool — returns the evidence chain, not just a boolean.
```ts
input: { slug: string, body?: "JCI" | "GHA" | "AACI" }
output: {
  results: [{
    body, status: "verified" | "expired" | "unverifiable",
    source_url, valid_until, checked_at
  }]
}
```
v1: reads from DB. v2: live-checks the accreditor's public registry.

### 4. `compare_procedures`
Cross-clinic price comparison for one procedure, optionally against a Canadian quote.
```ts
input: {
  procedure_code: string,
  canadian_quote_cad?: number,
  country?: "TR" | "MX"
}
output: {
  procedure: { code, name, typical_visits, recovery_days_onsite },
  options: [{ clinic_slug, clinic_name, price_range_usd, savings_vs_quote_pct | null }],
  fx_rate_used: { cad_usd: number, as_of: string }
}
```

### 5. `list_procedures`
Simple reference lookup so the agent can map free-text intake ("I need my whole top row redone") to a `procedure_code`.
```ts
input: { category?: string }
output: { procedures: [{ code, name, category, typical_visits, recovery_days_onsite }] }
```

---

## Guardrails (bake into the server, mention in the README)

- The server returns **information only**. No tool recommends a treatment, interprets symptoms, or ranks clinics by clinical outcome. Comparison is on price, accreditation, and logistics.
- Every accreditation row must carry a `source_url`. No source, no row.
- Stale pricing (`last_verified` > 90 days) is returned with a `stale: true` flag.
- Disclaimer string included in every tool response envelope: `"Informational only — not medical advice. Verify directly with the clinic."`

## Seed data plan

15 clinics: 8 Istanbul, 7 Mexico (Los Algodones skews high-volume dental). Source from JCI's public directory (jointcommissioninternational.org → accredited organizations), GHA's directory, and cross-check clinic websites. Budget ~4–6 hours of manual research. Store the research in `seed/clinics.yaml`, load via a Drizzle seed script.

## Build order

1. `pnpm init` monorepo, shared package with Drizzle schema, push to Supabase
2. Seed script + 3 clinics of real data (prove the pipeline before doing all 15)
3. MCP server: `list_procedures` → `search_clinics` → `get_clinic_profile` → `compare_procedures` → `verify_accreditation`
4. Vitest: one test file per tool, run against a seeded local Postgres (Docker)
5. Finish seed data to 15 clinics
6. README: architecture diagram, tool table, GIF of Claude calling the tools
7. Connect to Claude Desktop as a local MCP server — this is your demo

## Definition of done (portfolio bar)

- [ ] All 5 tools pass tests
- [ ] Server connects to Claude Desktop and answers "find me an accredited all-on-4 clinic in Istanbul under $8K"
- [ ] README a stranger can follow to run it locally
- [ ] 30-sec demo GIF
- [ ] Write-up drafted for kuldeepsinghtanwar.com

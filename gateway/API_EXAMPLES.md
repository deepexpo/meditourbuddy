# API examples

Base URL (local dev): `http://localhost:8000`

All endpoints except `/health`, `POST /auth/register`, and `POST /auth/login`
require `Authorization: Bearer <token>`.

The primary flow for the app is **register → login → `POST /cases`** — the
agent picks which registry tools to call. `GET /mcp/tools` / `POST /mcp/call`
still work (unchanged) for debugging or a future power-user/admin screen, but
you shouldn't need to call tools directly for the main product flow anymore.

## 1. Register

```
POST /auth/register
Content-Type: application/json
```
```json
{ "email": "patient@example.com", "password": "correct-horse-battery" }
```
Password must be at least 10 characters.

Success `201` (this also logs you in — no separate login call needed):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "ead64a93-80d5-48e9-badf-fa3cdc8291d8",
    "email": "patient@example.com",
    "created_at": "2026-07-19T06:05:49.433862Z"
  }
}
```

Failure `409` (email already registered):
```json
{ "detail": "An account with this email already exists", "code": "email_taken" }
```

Failure `422` (password too short — see §9, this shape is different from the
others):
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "password"],
      "msg": "String should have at least 10 characters",
      "input": "short",
      "ctx": { "min_length": 10 }
    }
  ]
}
```

## 2. Login

```
POST /auth/login
Content-Type: application/json
```
```json
{ "email": "patient@example.com", "password": "correct-horse-battery" }
```

Success `200`: same shape as register's success response.

Failure `401` (wrong password OR unknown email — intentionally the same
error either way, so you can't probe which emails are registered):
```json
{ "detail": "Invalid email or password", "code": "invalid_credentials" }
```

Token expires after `JWT_EXPIRE_MINUTES` (default 60 min) — re-login when
your app gets a 401.

## 3. Logout

```
POST /auth/logout
Authorization: Bearer <token>
```
Success `204` (no body).

This invalidates **every** active session for the account, not just the
token used to call it — there's no per-device session tracking, so if the
same account is logged in on two devices, calling this from either one logs
both out. After this call, delete the token from Keychain; it will now get
a `401` on any authenticated request even though it hasn't expired yet.
Logging in again issues a normal new working token.

## 4. Current user

```
GET /auth/me
Authorization: Bearer <token>
```
Success `200`:
```json
{
  "id": "ead64a93-80d5-48e9-badf-fa3cdc8291d8",
  "email": "patient@example.com",
  "created_at": "2026-07-19T06:05:49.433862Z"
}
```

```
DELETE /auth/me
Authorization: Bearer <token>
```
Success `204` (no body). This **hard-deletes** the account and cascades to
all of that user's cases and reports — irreversible, so confirm in the UI
before calling it. The token used to delete stops working immediately.

## 5. Create a case (the agent)

```
POST /cases
Authorization: Bearer <token>
Content-Type: application/json
```
```json
{
  "description": "I need a single dental implant, looking to save money by traveling abroad.",
  "canadian_quote_cad": 4500,
  "destination_preference": "TR",
  "budget_usd_max": 2000,
  "language": "en"
}
```
Only `description` is required. `destination_preference` is `"TR"`, `"MX"`,
or `"any"` (default). `canadian_quote_cad` and `budget_usd_max` are optional
numbers; omit `canadian_quote_cad` if the patient has no existing quote to
compare against.

This call runs a real multi-round Claude tool-use loop against the live
clinic registry — expect it to take several seconds, and show a loading
state, not a spinner-blocks-everything UI. There's a hard 60s server-side
timeout (`CASE_TIMEOUT_SECONDS`).

Success `201` (illustrative — the model chooses which/how many options
based on real registry data, so exact contents vary per run):
```json
{
  "id": "54ad2c13-1212-4cee-8d73-7f2e9bb3ce36",
  "status": "complete",
  "created_at": "2026-07-19T06:13:11.095783Z",
  "completed_at": "2026-07-19T06:13:14.912004Z",
  "failure_reason": null,
  "intake": {
    "description": "I need a single dental implant, looking to save money by traveling abroad.",
    "canadian_quote_cad": 4500,
    "destination_preference": "TR",
    "budget_usd_max": 2000,
    "language": "en"
  },
  "report": {
    "case_summary": "A single dental implant in Turkey typically costs a fraction of the Canadian quote provided, with several accredited clinics available in Istanbul.",
    "procedure": {
      "code": "IMPLANT_SINGLE",
      "name": "Single Dental Implant",
      "typical_visits": 2,
      "recovery_days_onsite": 3
    },
    "options": [
      {
        "clinic": { "name": "Vera Smile Dental Clinic", "city": "Istanbul", "country": "TR", "slug": "vera-smile-istanbul" },
        "accreditations": [
          { "body": "ISO_9001", "valid_until": null, "source_url": "https://www.verasmile.com/our-quality-standarts/" }
        ],
        "price_usd": { "min": 450, "max": 800 },
        "savings_vs_quote_pct": 82.0,
        "trip_notes": "2 visits required; plan for 3 days of on-site recovery between them."
      }
    ],
    "next_steps": [
      "Contact the clinic directly to confirm current availability and get a written quote.",
      "Consult your own dentist before committing to any procedure."
    ]
  },
  "disclaimer": "Informational only — not medical advice. MediTourBuddy does not recommend treatments. Verify all details directly with the clinic and consult your own dentist.",
  "trace": [
    { "round": 0, "tool": "list_procedures", "args": {} },
    { "round": 1, "tool": "search_clinics", "args": { "procedure_code": "IMPLANT_SINGLE", "country": "TR", "max_budget_usd": 2000 } },
    { "round": 2, "tool": "verify_accreditation", "args": { "slug": "vera-smile-istanbul" } }
  ]
}
```
`options` can legitimately be `[]` — the agent is instructed to say so
honestly rather than stretch a bad match, so render a real "no matches
found" empty state, not an error.

Failure `504` (agent exceeded the timeout):
```json
{ "detail": "Agent run timed out", "code": "case_timeout" }
```

Failure `502` (tool/model/validation failure — real captured example, this
one from a misconfigured API key):
```json
{ "detail": "Agent failed to produce a report", "code": "case_failed" }
```
On either failure, the case itself was still persisted with
`"status": "failed"` and a `failure_reason` string — `GET /cases/{id}`
still works and shows why it failed, it just has no `report`.

## 6. List / get / delete cases

```
GET /cases
Authorization: Bearer <token>
```
Success `200` — the caller's own cases, newest first, **without** the full
report (use `GET /cases/{id}` for that — keeps the list screen light):
```json
[
  {
    "id": "54ad2c13-1212-4cee-8d73-7f2e9bb3ce36",
    "status": "failed",
    "created_at": "2026-07-19T06:13:11.095783Z",
    "completed_at": "2026-07-19T06:13:11.868598Z",
    "failure_reason": "Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}, 'request_id': 'req_011CdAvUyVPDBMtWDLzVczAy'}"
  }
]
```

```
GET /cases/{id}
Authorization: Bearer <token>
```
Success `200`: same full shape as the `POST /cases` response.

Failure `404` — case doesn't exist **or belongs to another user** (both
look identical, on purpose — never reveal that a case ID exists):
```json
{ "detail": "Case not found", "code": "case_not_found" }
```

```
DELETE /cases/{id}
Authorization: Bearer <token>
```
Success `204` (no body). Same 404 behavior as above for a case you don't own.

## 7. List available tools (debug/advanced)

```
GET /mcp/tools
Authorization: Bearer <token>
```

Success `200` (trimmed):
```json
{
  "tools": [
    { "name": "list_procedures", "description": "...", "inputSchema": { "...": "..." } },
    { "name": "search_clinics", "description": "...", "inputSchema": { "required": ["procedure_code"] } },
    { "name": "get_clinic_profile", "description": "...", "inputSchema": { "required": ["slug"] } },
    { "name": "compare_procedures", "description": "...", "inputSchema": { "required": ["procedure_code"] } },
    { "name": "verify_accreditation", "description": "...", "inputSchema": { "required": ["slug"] } }
  ]
}
```
Use `inputSchema`/`outputSchema` on each tool to drive form validation and
rendering in your app — they're full JSON Schema.

## 8. Call a tool directly (debug/advanced)

```
POST /mcp/call
Authorization: Bearer <token>
Content-Type: application/json
```
```json
{ "name": "<tool name>", "arguments": { "...": "..." } }
```

Response shape is always the same envelope — MCP's content array:
```json
{
  "result": [
    { "type": "text", "text": "<JSON-encoded string — parse this>", "annotations": null, "meta": null }
  ]
}
```

**Important:** `result[0].text` is a JSON *string*, not a nested object. Your
app must `JSON.parse()` (or equivalent) it to get the actual data.

### Example: search_clinics

Request:
```json
{
  "name": "search_clinics",
  "arguments": { "procedure_code": "IMPLANT_ALL_ON_4", "country": "TR", "max_budget_usd": 8000 }
}
```

`result[0].text`, parsed:
```json
{
  "clinics": [
    {
      "slug": "maltepe-dental-istanbul",
      "name": "Maltepe Dental Clinic",
      "city": "Istanbul",
      "country": "TR",
      "accreditations": ["ISO_9001"],
      "price_range_usd": { "min": 3203.2, "max": 3203.2, "stale": false },
      "practitioner_count": 1,
      "verified_at": null
    },
    {
      "slug": "vera-smile-istanbul",
      "name": "Vera Smile Dental Clinic",
      "city": "Istanbul",
      "country": "TR",
      "accreditations": ["ISO_9001"],
      "price_range_usd": { "min": 4000.0, "max": 7436.0, "stale": false },
      "practitioner_count": 1,
      "verified_at": null
    }
  ],
  "disclaimer": "Informational only — not medical advice. Verify directly with the clinic."
}
```

### Example: get_clinic_profile

Request:
```json
{ "name": "get_clinic_profile", "arguments": { "slug": "vera-smile-istanbul" } }
```

`result[0].text`, parsed (trimmed):
```json
{
  "clinic": {
    "id": "add6d3c9-8569-4ee6-979a-475fe198dd98",
    "slug": "vera-smile-istanbul",
    "name": "Vera Smile Dental Clinic",
    "country": "TR",
    "city": "Istanbul",
    "address": "Kordonboyu, Turgut Özal Blv. No 47, Kat:3, 34860 Kartal/İstanbul, Türkiye",
    "languages": ["en", "tr", "ru", "fr", "de", "es", "it", "pt", "ar"],
    "year_established": 2013,
    "website": "https://www.verasmile.com/",
    "verified_at": null
  },
  "accreditations": [
    { "body": "ISO_9001", "reference_id": null, "valid_until": null, "source_url": "https://www.verasmile.com/our-quality-standarts/" }
  ],
  "practitioners": [
    { "full_name": "Nurlan Gasimov", "title": "General & Cosmetic Dentist", "years_experience": 12 }
  ],
  "procedures": [
    {
      "code": "IMPLANT_SINGLE", "name": "Single Dental Implant",
      "price_min": 450, "price_max": 800, "currency": "EUR",
      "includes": ["implant_screw", "abutment", "crown"],
      "last_verified": "2026-07-16", "stale": false
    }
  ],
  "disclaimer": "Informational only — not medical advice. Verify directly with the clinic."
}
```

### Example: list_procedures (no required args)

Request:
```json
{ "name": "list_procedures", "arguments": {} }
```

`result[0].text`, parsed (trimmed):
```json
{
  "procedures": [
    { "code": "IMPLANT_SINGLE", "name": "Single Dental Implant", "category": "implant", "typical_visits": 2, "recovery_days_onsite": 3 },
    { "code": "IMPLANT_ALL_ON_4", "name": "All-on-4 Full Arch Implants", "category": "implant", "typical_visits": 2, "recovery_days_onsite": 5 }
  ],
  "disclaimer": "Informational only — not medical advice. Verify directly with the clinic."
}
```

## 9. Error handling — three different shapes

**1. Domain errors** (auth/cases business logic) — a flat object with both
`detail` (human-readable) and `code` (machine-readable, stable, safe to
switch on):
```json
{ "detail": "Invalid email or password", "code": "invalid_credentials" }
```
| `code` | HTTP status | Meaning |
|---|---|---|
| `email_taken` | 409 | Register with an email already in use |
| `invalid_credentials` | 401 | Login with wrong email or unknown email |
| `case_not_found` | 404 | Case doesn't exist, or belongs to another user |
| `case_timeout` | 504 | Agent run exceeded the server-side timeout |
| `case_failed` | 502 | Agent/tool/model failure producing a report |
| `http_error` | varies | Generic fallback — e.g. missing/expired/invalid/logged-out Bearer token (401) |

**2. Request validation errors** (malformed JSON body — e.g. missing
required field, password too short) — FastAPI's own shape, `detail` is an
**array of objects**, not a string, and there's no `code` field at all:
```json
{
  "detail": [
    { "type": "missing", "loc": ["body", "description"], "msg": "Field required", "input": {} }
  ]
}
```
Check whether `detail` is a string or an array to tell these two apart.

**3. Tool-level errors** (only from `POST /mcp/call`, §8 — bad tool name or
bad arguments per the tool's own validation) come back as `200 OK` with the
error *inside* the content array:
```json
{
  "result": [
    { "type": "text", "text": "MCP error -32602: Tool nonexistent_tool not found", "annotations": null, "meta": null }
  ]
}
```
There's no structured `error` field to branch on — treat `result[0].text`
starting with `MCP error` as a failure case, or wrap parsing in a try/catch
and surface the raw string if `JSON.parse` fails. `POST /cases` doesn't
have this problem — the agent already handles tool failures internally and
either produces a real report or a `case_failed`/502.

## Quick reference: curl

```bash
# Register (or use /auth/login on subsequent runs)
TOKEN=$(curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"patient@example.com","password":"correct-horse-battery"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Run a case
curl -s -X POST http://localhost:8000/cases \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"description":"Need a single dental implant, exploring options abroad.","canadian_quote_cad":4500,"destination_preference":"TR","budget_usd_max":2000}'

# List past cases
curl -s http://localhost:8000/cases -H "Authorization: Bearer $TOKEN"

# (debug) list/call tools directly
curl -s http://localhost:8000/mcp/tools -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://localhost:8000/mcp/call \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"search_clinics","arguments":{"procedure_code":"IMPLANT_ALL_ON_4","country":"TR","max_budget_usd":8000}}'

# Logout — invalidates $TOKEN (and every other session on this account)
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer $TOKEN"
```

# API examples

Base URL (local dev): `http://localhost:8000`

All endpoints except `/health`, `POST /auth/register`, `POST /auth/login`,
and the two `POST /auth/password-reset/*` endpoints (§3 — the whole point
of password reset is the user is locked out) require
`Authorization: Bearer <token>`.

The primary flow for the app is **register → login → `POST /cases`**. One
screen, one endpoint, both tiers — `POST /cases` branches server-side on the
account's `tier` and always returns the same `Report` shape (§6), so the
client renders by *field presence*, not by tier:

```
                    ┌─ tier=free ────► basic_pipeline()  (deterministic, no LLM, <2s)
POST /cases ── auth ┤
                    └─ tier=premium ─► agent loop         (Claude + tools, several seconds)
```

`GET /mcp/tools` / `POST /mcp/call` are **admin/debug only now** (§9b) — the
client should not call them. Use the typed routes instead: `GET /procedures`,
`GET /clinics/search`, `GET /clinics/{slug}` (§8). They wrap the same
registry tools but return clean JSON — no `result[0].text` double-parse.

## 1. Register

```
POST /auth/register
Content-Type: application/json
```
```json
{ "email": "patient@example.com", "password": "correct-horse-battery", "consent_accepted": true }
```
Password must be at least `PASSWORD_MIN_LENGTH` characters (default **8**).
`consent_accepted` must be **literally `true`** — this is where the
client's consent screen ("informational only — MediTourBuddy is not a
medical service provider") gets recorded server-side; `false` or omitting
the field entirely both fail registration (§1 failure example below).

Success `201` (this also logs you in — no separate login call needed):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "ead64a93-80d5-48e9-badf-fa3cdc8291d8",
    "email": "patient@example.com",
    "tier": "free",
    "role": "user",
    "created_at": "2026-07-19T06:05:49.433862Z"
  }
}
```
New accounts always start on `tier: "free"`, `role: "user"`. `role` is
`"user"` | `"admin"` | `"support"` — `"support"` is reserved for future use
(no endpoint treats it differently from `"user"` yet). There's no
self-serve tier upgrade or role grant this phase — both are flipped by SQL
only (see §6c). Use `user.tier`/`user.role` to decide UI up front (e.g.
whether to even attempt the upgrade sheet, or show an admin-only screen);
`access_token`'s JWT also carries `tier`/`role` as claims if you need them
without a round-trip, but the response body is the easier source.

Failure `409` (email already registered):
```json
{ "detail": "An account with this email already exists", "code": "email_taken" }
```

Failure `422` (password too short, or `consent_accepted` false/missing —
see §12, this shape is different from the others; real captured examples):
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "password"],
      "msg": "Value error, Password must be at least 8 characters",
      "input": "short",
      "ctx": { "error": "Password must be at least 8 characters" }
    }
  ]
}
```
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "consent_accepted"],
      "msg": "Value error, You must accept the consent terms to register.",
      "input": false,
      "ctx": { "error": "You must accept the consent terms to register." }
    }
  ]
}
```
Both are `type: "value_error"` (a custom validator), not `string_too_short`
— parse `msg`/`loc` rather than assuming a specific `type` or `ctx` shape
per field.

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

**`tier`/`role` are snapshotted into the token at login/register, not
re-read per request.** If an account is upgraded to premium (or granted
admin) via SQL while a token is still live, that token keeps behaving as the
old tier/role until it expires or the user logs out/in again. If you build an
"upgrade requested" flow, tell the user to log out and back in to pick up
the change — don't expect it to take effect mid-session.

## 3. Password reset

Two calls, no auth needed on either (the whole point is the user is locked
out). A 6-digit code emailed to them, entered in-app alongside the new
password — no deep-linking/universal-links setup required.

### 3a. `POST /auth/password-reset/request`

```
POST /auth/password-reset/request
Content-Type: application/json
```
```json
{ "email": "patient@example.com" }
```
Success `204` (no body) — **always**, whether or not that email is
registered. Same anti-enumeration principle as login's identical
wrong-password-vs-unknown-email error (§2): don't build UI that reveals
"no account with that email" here, just show "if that email is registered,
a code is on its way."

The code expires in `PASSWORD_RESET_CODE_TTL_MINUTES` (default 15). Only
the most recently requested code is ever valid — requesting again
invalidates any earlier one. Requesting more than
`PASSWORD_RESET_REQUESTS_PER_HOUR` (default 5) times in an hour for the
same account is silently rate-limited (still `204`, no new code/email sent)
— don't build a "resend" button with no cooldown.

### 3b. `POST /auth/password-reset/confirm`

```
POST /auth/password-reset/confirm
Content-Type: application/json
```
```json
{ "email": "patient@example.com", "code": "483920", "new_password": "correct-horse-battery" }
```
`new_password` follows the same length rule as registration (§1). Success
`204` (no body) — the password is changed and, importantly, **every
existing session is invalidated** (same mechanism as `POST /auth/logout`,
§4), including the session on the device making this call. Send the user
straight to the login screen, not back into the app.

Failure `400` — one generic error for every failure reason (wrong code,
expired code, too many wrong attempts, no code requested) so a client can't
learn which:
```json
{ "detail": "Invalid or expired reset code", "code": "invalid_reset_code" }
```
A code is permanently burned (even the right code stops working) after
`PASSWORD_RESET_MAX_ATTEMPTS` wrong guesses (default 5) — at that point the
user needs to call §3a again for a fresh one.

## 4. Logout

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

## 5. Current user

```
GET /auth/me
Authorization: Bearer <token>
```
Success `200`:
```json
{
  "id": "ead64a93-80d5-48e9-badf-fa3cdc8291d8",
  "email": "patient@example.com",
  "tier": "free",
  "role": "user",
  "created_at": "2026-07-19T06:05:49.433862Z"
}
```
This reads `tier`/`role` live from the DB (unlike the JWT claims, which
are frozen at login) — useful for detecting "you were upgraded, please
re-login" without waiting for a 401/403 to surface it.

```
DELETE /auth/me
Authorization: Bearer <token>
```
Success `204` (no body). This **hard-deletes** the account and cascades to
all of that user's cases and reports — irreversible, so confirm in the UI
before calling it. The token used to delete stops working immediately.

## 6. Create a case

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
compare against. **The request body is identical for both tiers** — the
account's `tier` decides what happens server-side, not the request.

- **Free**: a deterministic keyword match on `description` → registry
  lookups. Zero Anthropic tokens, typically completes in 1–3s.
- **Premium**: a two-phase agent run against the live clinic registry —
  Claude retrieves and verifies candidate clinics via tool calls, then a
  separate, tightly-scoped call writes the report from *only* that
  verified data (not from its memory of the retrieval conversation).
  `budget_usd_max` is enforced the same way free tier enforces it: an
  over-budget clinic is filtered out before the model can ever offer it,
  not just requested politely in a prompt. Takes several seconds — show a
  loading state, not a spinner-blocks-everything UI.
- **Admin** (`role: "admin"`): always gets the premium engine and never
  hits the quota, regardless of their own account's `tier`. Send
  `"preview_tier": "free"` or `"preview_tier": "premium"` (admin-only —
  silently ignored for everyone else) to preview either report shape on
  demand for a stakeholder demo, without touching the admin's own `tier`
  column. Previewing `"free"` runs the real `basic_pipeline`, complete with
  `locked_features` populated — it's not a mocked/fake version of the free
  report, it's the actual one.

Both share a hard 60s server-side timeout (`CASE_TIMEOUT_SECONDS`).

### 6a. Success `201` — the unified `Report` shape

Every field below is present on **both** tiers; the difference is which
ones are populated. Render each section by whether its field is non-null,
not by checking `report_tier`.

Free-tier response (real captured example):
```json
{
  "id": "6a4b9fb5-e7b3-4dda-be71-6ddc67823225",
  "status": "complete",
  "created_at": "2026-07-20T01:58:17.609215Z",
  "completed_at": "2026-07-20T01:58:20.332896Z",
  "failure_reason": null,
  "intake": {
    "description": "I need an all-on-4 full arch implant, budget around $10000 USD",
    "canadian_quote_cad": null,
    "destination_preference": "any",
    "budget_usd_max": null,
    "language": "en"
  },
  "report": {
    "report_tier": "basic",
    "case_summary": "Based on your description, we matched this to All-on-4 Full Arch Implants. Here are the top 3 accredited option(s) found, ranked by accreditation strength and price.",
    "procedure": {
      "code": "IMPLANT_ALL_ON_4",
      "name": "All-on-4 Full Arch Implants",
      "typical_visits": 2,
      "recovery_days_onsite": 5
    },
    "options": [
      {
        "clinic": { "name": "Maltepe Dental Clinic", "city": "Istanbul", "country": "TR", "slug": "maltepe-dental-istanbul" },
        "accreditations": [
          { "body": "ISO_9001", "valid_until": null, "source_url": "https://www.maltepedentalclinic.com/about-us/quality-standards/" }
        ],
        "price_usd": { "min": 3203.2, "max": 3203.2 },
        "savings_vs_quote_pct": null,
        "trip_notes": null,
        "trip_plan": null,
        "all_in_cad": null
      }
    ],
    "next_steps": [
      "Review the clinics below and their accreditation evidence.",
      "Contact a clinic directly to confirm current pricing and availability.",
      "Upgrade to Premium for a full itinerary and all-in cost estimate."
    ],
    "locked_features": ["custom_plan", "trip_plan", "all_in_cost", "agent_analysis"],
    "disclaimer": "Informational only — not medical advice. MediTourBuddy does not recommend treatments. Verify all details directly with the clinic and consult your own dentist.",
    "trace": null
  }
}
```

Premium-tier response (same request, premium account — trimmed; the model
chooses which/how many options based on real registry data, so exact
contents vary per run):
```json
{
  "id": "8ea20b87-b5e1-42f8-80c9-0bc5459c1006",
  "status": "complete",
  "created_at": "2026-07-20T02:04:25.794323Z",
  "completed_at": "2026-07-20T02:05:10.406962Z",
  "failure_reason": null,
  "intake": { "...": "same shape as above" },
  "report": {
    "report_tier": "full",
    "case_summary": "The patient is a Canadian seeking a single dental implant in Turkey with a budget of approximately $4,000 USD. One accredited clinic in Istanbul was identified and independently verified via JCI.",
    "procedure": { "code": "IMPLANT_SINGLE", "name": "Single Dental Implant", "typical_visits": 2, "recovery_days_onsite": 3 },
    "options": [
      {
        "clinic": { "name": "Acıbadem Maslak Hospital", "city": "Istanbul", "country": "TR", "slug": "acibadem-maslak-istanbul" },
        "accreditations": [
          { "body": "JCI", "valid_until": null, "source_url": "https://acibademinternational.com/hospital/maslak-hospital/" }
        ],
        "price_usd": { "min": 600.0, "max": 1200.0 },
        "savings_vs_quote_pct": null,
        "trip_notes": "2 visits required (implant placement + crown fitting); plan for approximately 3 days on-site per visit.",
        "trip_plan": null,
        "all_in_cad": null
      }
    ],
    "next_steps": [
      "Contact Acıbadem Maslak International directly to request a personalised treatment plan and itemised quote.",
      "Verify your Canadian travel insurance for dental-complication coverage abroad."
    ],
    "locked_features": null,
    "disclaimer": "Informational only — not medical advice. MediTourBuddy does not recommend treatments. Verify all details directly with the clinic and consult your own dentist.",
    "trace": [
      { "round": 0, "tool": "list_procedures", "args": { "category": "implant" } },
      { "round": 1, "tool": "search_clinics", "args": { "procedure_code": "IMPLANT_SINGLE", "country": "TR", "max_budget_usd": 4000 } },
      { "round": 2, "tool": "verify_accreditation", "args": { "slug": "acibadem-maslak-istanbul", "body": "JCI" } }
    ]
  }
}
```

Field-by-field:
| Field | Free | Premium | Notes |
|---|---|---|---|
| `report_tier` | `"basic"` | `"full"` | The only field you'd branch on, and only for analytics/labeling — not for rendering. |
| `locked_features` | array of feature keys | `null` | Render each key's card in its natural position as a locked/blurred teaser; tap → upgrade sheet. Log the tap (§11a). Data-driven: don't hardcode which features are locked. |
| `trace` | `null` | array | Which tools ran, in order — demo/debug value, not for end users. |
| `options[].trip_notes` / `trip_plan` / `all_in_cad` | always `null` | populated (`trip_plan`/`all_in_cad` are `null` until travel-mcp lands even on premium) | Render the section only if non-null. |
| everything else (`case_summary`, `procedure`, `options[].clinic`/`accreditations`/`price_usd`/`savings_vs_quote_pct`, `next_steps`, `disclaimer`) | populated | populated | Same shape both tiers. |

`options` can legitimately be `[]` on either tier — say so honestly rather
than stretch a bad match, so render a real "no matches found" empty state,
not an error.

### 6b. Failure `422` — free tier, description didn't match a procedure

```json
{
  "detail": "Could not determine procedure from description",
  "code": "PROCEDURE_UNCLEAR",
  "choices": [
    { "code": "IMPLANT_SINGLE", "name": "Single Dental Implant", "category": "implant", "typical_visits": 2, "recovery_days_onsite": 3 },
    { "code": "IMPLANT_ALL_ON_4", "name": "All-on-4 Full Arch Implants", "category": "implant", "typical_visits": 2, "recovery_days_onsite": 5 }
  ]
}
```
Only free-tier accounts can hit this — premium's agent infers the procedure
itself. Show a procedure picker populated from `choices`; when the patient
picks one, resubmit `POST /cases` with `description` rewritten to include
that procedure's exact `name` (e.g. `"Single Dental Implant"`) so the
keyword matcher resolves it deterministically — there's no separate
`procedure_code` field on the request, the matcher only reads `description`.
No case row is created and no quota is consumed for this response.

### 6c. Failure `429` — quota exceeded

```json
{ "detail": "Quota exceeded for your tier", "code": "QUOTA_EXCEEDED" }
```
Free: 10 cases/day. Premium: 10 agent runs/month. `role: "admin"` accounts
never hit this, regardless of their own tier or usage. No case row is
created. There's no client-visible "quota remaining" field yet — treat this
as a terminal state for the request and prompt to retry later (free) or
contact you about premium limits (premium). Tiers/roles are flipped by SQL
only right now (no self-serve upgrade), so a premium quota bump is a manual
op on your end.

### 6d. Failure `504` (agent exceeded the timeout)
```json
{ "detail": "Agent run timed out", "code": "case_timeout" }
```

### 6e. Failure `502` (tool/model/validation failure — real captured example,
this one from a misconfigured API key)
```json
{ "detail": "Agent failed to produce a report", "code": "case_failed" }
```
On either 504 or 502, the case itself was still persisted with
`"status": "failed"` and a `failure_reason` string — `GET /cases/{id}`
still works and shows why it failed, it just has no `report`.

## 7. List / get / delete cases

```
GET /cases
Authorization: Bearer <token>
```
Success `200` — the caller's own cases, newest first, **without** the full
report (use `GET /cases/{id}` for that — keeps the list screen light).
**Free tier only ever gets the most recent 1 case back here**, even if more
exist — `GET /cases/{id}` still works for any of the caller's own older
cases by ID, this only limits the list view. Premium is unlimited, and so
is `role: "admin"` regardless of their own tier. If you
want a "see all history" locked card in the history screen, that's a
client-side decision (there's no `total_count` in the response to compare
against — track it another way, or just always show the teaser for free
accounts):
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

## 8. Browse clinics/procedures directly (search, clinic profile screens)

Thin typed wrappers around the registry — use these instead of `/mcp/call`
(now admin-only, §9) for any client-facing browse/search screen. Clean JSON
in, clean JSON out; no `result[0].text` double-parse.

### 8a. `GET /procedures`

```
GET /procedures?category=implant
Authorization: Bearer <token>
```
`category` is optional (`implant` | `restorative` | `cosmetic` | `surgical`).
Success `200`:
```json
{
  "procedures": [
    { "code": "IMPLANT_SINGLE", "name": "Single Dental Implant", "category": "implant", "typical_visits": 2, "recovery_days_onsite": 3 },
    { "code": "IMPLANT_ALL_ON_4", "name": "All-on-4 Full Arch Implants", "category": "implant", "typical_visits": 2, "recovery_days_onsite": 5 }
  ]
}
```
Server-cached for up to 1h — don't poll this aggressively, it won't change
faster than that anyway.

### 8b. `GET /clinics/search`

```
GET /clinics/search?procedure_code=IMPLANT_ALL_ON_4&country=TR&max_budget_usd=8000
Authorization: Bearer <token>
```
Query params: `procedure_code` (required), `country` (`TR`|`MX`, optional),
`max_budget_usd` (optional), `language` (default `en`),
`require_accreditation` (default `true`).

Success `200`:
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
    }
  ],
  "disclaimer": "Informational only — not medical advice. Verify directly with the clinic."
}
```
Note `accreditations` here is just body names (`["JCI"]`) — no `source_url`.
For the full evidence chain, follow up with `GET /clinics/{slug}` (§8c).

### 8c. `GET /clinics/{slug}`

```
GET /clinics/vera-smile-istanbul
Authorization: Bearer <token>
```
Success `200` (trimmed):
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
This is where `source_url`/`valid_until` for each accreditation live — the
`POST /cases` report already inlines this per-option, so you only need this
route standalone for a dedicated clinic-profile screen.

## 9. Admin/debug: raw MCP tool access

`/mcp/tools` and `/mcp/call` now require `role: "admin"` on the account
(§5) — any other account (including `"support"`) gets `403 {"detail":
"Admin access required", "code": "forbidden"}`. **The client app should not
call these** — use the typed routes in §8 instead. Kept here for an
internal admin/debug screen or manual testing against tools that don't have
a typed wrapper yet (`compare_procedures`, `verify_accreditation`).

### 9a. `GET /mcp/tools`

```
GET /mcp/tools
Authorization: Bearer <token>   (admin account)
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
rendering in an admin screen — they're full JSON Schema.

### 9b. `POST /mcp/call`

```
POST /mcp/call
Authorization: Bearer <token>   (admin account)
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

`search_clinics`, `get_clinic_profile`, and `list_procedures` have typed
wrappers now (§8) — prefer those. The two tools below don't yet, so this is
still the only way to reach them:

### Example: compare_procedures

Request:
```json
{
  "name": "compare_procedures",
  "arguments": { "procedure_code": "IMPLANT_SINGLE", "canadian_quote_cad": 4500, "country": "TR" }
}
```

`result[0].text`, parsed:
```json
{
  "procedure": { "code": "IMPLANT_SINGLE", "name": "Single Dental Implant", "typical_visits": 2, "recovery_days_onsite": 3 },
  "options": [
    { "clinic_slug": "vera-smile-istanbul", "clinic_name": "Vera Smile Dental Clinic", "price_range_usd": { "min": 450, "max": 800, "stale": false }, "savings_vs_quote_pct": 82.0 }
  ],
  "fx_rate_used": { "cad_usd": 0.73, "as_of": "2026-06-01" },
  "disclaimer": "Informational only — not medical advice. Verify directly with the clinic."
}
```

### Example: verify_accreditation

Request:
```json
{ "name": "verify_accreditation", "arguments": { "slug": "acibadem-maslak-istanbul", "body": "JCI" } }
```

`result[0].text`, parsed:
```json
{
  "results": [
    { "body": "JCI", "status": "verified", "source_url": "https://acibademinternational.com/hospital/maslak-hospital/", "valid_until": null, "checked_at": "2026-07-20T02:04:52.101Z" }
  ],
  "disclaimer": "Informational only — not medical advice. Verify directly with the clinic."
}
```

## 10. Admin: users and case history

All four routes require `role: "admin"` on the caller — same gating as §9,
`403 {"detail": "Admin access required", "code": "forbidden"}` for anyone
else. Not for the client app's main flow — this is for an internal
admin/support screen.

### 10a. `GET /admin/users`

```
GET /admin/users
Authorization: Bearer <token>   (admin account)
```
Success `200` — every registered user, newest first, same shape as `GET
/auth/me` (§5):
```json
[
  { "id": "ead64a93-80d5-48e9-badf-fa3cdc8291d8", "email": "patient@example.com", "tier": "free", "role": "user", "created_at": "2026-07-19T06:05:49.433862Z" }
]
```
No pagination yet — fine at this phase's user count, revisit before it
isn't.

### 10b. `GET /admin/users/{user_id}`

```
GET /admin/users/ead64a93-80d5-48e9-badf-fa3cdc8291d8
Authorization: Bearer <token>   (admin account)
```
Success `200`: single user, same shape as one entry of §10a. Failure `404`:
```json
{ "detail": "User not found", "code": "user_not_found" }
```

### 10c. `GET /admin/users/{user_id}/cases`

```
GET /admin/users/ead64a93-80d5-48e9-badf-fa3cdc8291d8/cases
Authorization: Bearer <token>   (admin account)
```
Success `200`: that user's **full** case history, same shape as `GET
/cases` (§7) — but unlike calling `/cases` as that user, there's no
free-tier 1-case cap here. An empty array just means they have no cases;
there's no 404 for "user has zero cases" (only §10b/§10d 404 on a missing
`user_id`/`case_id`).

### 10d. `GET /admin/users/{user_id}/cases/{case_id}`

```
GET /admin/users/ead64a93-80d5-48e9-badf-fa3cdc8291d8/cases/6a4b9fb5-e7b3-4dda-be71-6ddc67823225
Authorization: Bearer <token>   (admin account)
```
Success `200`: full `CaseDetail`, same shape as `GET /cases/{id}` (§7) —
complete `report` included. Failure `404` (case doesn't exist, or exists
but doesn't belong to that `user_id`):
```json
{ "detail": "Case not found", "code": "case_not_found" }
```

## 11. Analytics

### 11a. `POST /analytics/locked-card-tap`

```
POST /analytics/locked-card-tap
Authorization: Bearer <token>
Content-Type: application/json
```
```json
{ "feature": "trip_plan" }
```
Fire this whenever a free-tier user taps a locked card (§6a) — `feature`
should be one of the strings from that report's `locked_features` array.
Success `204` (no body). This is server-side signal for "which lock gets
tapped most = what people would pay for" — no response to act on client-side.

## 12. Error handling — three different shapes

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
| `invalid_reset_code` | 400 | Wrong/expired/already-used/too-many-attempts reset code (§3b) |
| `PROCEDURE_UNCLEAR` | 422 | Free tier: `description` didn't match a known procedure — has a `choices` array (§6b) |
| `QUOTA_EXCEEDED` | 429 | Free: 10 cases/day. Premium: 10 agent runs/month (§6c) |
| `case_not_found` | 404 | Case doesn't exist, or belongs to another user |
| `user_not_found` | 404 | `GET /admin/users/{user_id}` — no such user (§10b) |
| `case_timeout` | 504 | Agent run exceeded the server-side timeout |
| `case_failed` | 502 | Agent/tool/model failure producing a report |
| `forbidden` | 403 | `/mcp/*` or `/admin/*` called by a non-admin account (§9, §10) |
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

**3. Tool-level errors** (only from `POST /mcp/call`, §9b — bad tool name or
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
# Register (or use /auth/login on subsequent runs) — new accounts are tier=free
TOKEN=$(curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"patient@example.com","password":"correct-horse-battery","consent_accepted":true}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Forgot password — always 204 (check the inbox for the 6-digit code)
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/auth/password-reset/request \
  -H "Content-Type: application/json" -d '{"email":"patient@example.com"}'
curl -s -X POST http://localhost:8000/auth/password-reset/confirm \
  -H "Content-Type: application/json" \
  -d '{"email":"patient@example.com","code":"483920","new_password":"new-correct-horse-battery"}'

# Run a case — same call for both tiers, response's report_tier tells you which ran
curl -s -X POST http://localhost:8000/cases \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"description":"Need a single dental implant, exploring options abroad.","canadian_quote_cad":4500,"destination_preference":"TR","budget_usd_max":2000}'

# List past cases (free tier: only the most recent 1 comes back)
curl -s http://localhost:8000/cases -H "Authorization: Bearer $TOKEN"

# Browse clinics/procedures (typed routes — any authenticated account)
curl -s "http://localhost:8000/procedures?category=implant" -H "Authorization: Bearer $TOKEN"
curl -s "http://localhost:8000/clinics/search?procedure_code=IMPLANT_ALL_ON_4&country=TR&max_budget_usd=8000" \
  -H "Authorization: Bearer $TOKEN"
curl -s http://localhost:8000/clinics/vera-smile-istanbul -H "Authorization: Bearer $TOKEN"

# Log a locked-card tap (free tier UI)
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/analytics/locked-card-tap \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"feature":"trip_plan"}'

# (admin/debug only — 403 for non-admin accounts) list/call tools directly
curl -s http://localhost:8000/mcp/tools -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://localhost:8000/mcp/call \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"compare_procedures","arguments":{"procedure_code":"IMPLANT_SINGLE","canadian_quote_cad":4500}}'

# (admin only) preview the free-tier report shape for a stakeholder demo —
# works even though this admin's own tier is premium
curl -s -X POST http://localhost:8000/cases \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"description":"Need a single dental implant, exploring options abroad.","preview_tier":"free"}'

# (admin only) browse other users and their case history — 403 for everyone else
curl -s http://localhost:8000/admin/users -H "Authorization: Bearer $ADMIN_TOKEN"
curl -s http://localhost:8000/admin/users/<user_id>/cases -H "Authorization: Bearer $ADMIN_TOKEN"

# Logout — invalidates $TOKEN (and every other session on this account)
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer $TOKEN"
```

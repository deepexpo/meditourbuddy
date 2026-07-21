-- Registration consent: records that the user agreed to the
-- informational-only / not-a-medical-service-provider consent screen.
-- Backfills existing rows to now() (this app has no real users yet);
-- going forward every INSERT sets it explicitly (see app/routers/auth.py).
--
-- Safe to re-run.

ALTER TABLE gateway.users
  ADD COLUMN IF NOT EXISTS consent_accepted_at timestamptz NOT NULL DEFAULT now();

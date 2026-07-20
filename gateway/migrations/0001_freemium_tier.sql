-- Freemium phase: adds tier/admin support to gateway.users, and makes
-- gateway.reports.trace nullable (the free engine has no agent trace).
--
-- No migration tooling is wired up in this repo yet (alembic is a listed
-- dependency but unconfigured) — run this by hand against Supabase, the
-- same way the rest of the gateway schema was created. Safe to re-run:
-- every statement is guarded so it's a no-op if already applied.

ALTER TABLE gateway.users
  ADD COLUMN IF NOT EXISTS tier text NOT NULL DEFAULT 'free';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_tier'
  ) THEN
    ALTER TABLE gateway.users
      ADD CONSTRAINT ck_users_tier CHECK (tier IN ('free', 'premium'));
  END IF;
END $$;

ALTER TABLE gateway.users
  ADD COLUMN IF NOT EXISTS is_admin boolean NOT NULL DEFAULT false;

ALTER TABLE gateway.reports
  ALTER COLUMN trace DROP NOT NULL;

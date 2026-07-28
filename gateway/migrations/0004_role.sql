-- Replaces gateway.users.is_admin with a three-value role column
-- ('user' | 'admin' | 'support') — tier (free/premium) stays a fully
-- independent axis. 'support' is reserved for future use; no endpoint
-- treats it differently from 'user' yet.
--
-- Safe to re-run.

ALTER TABLE gateway.users
  ADD COLUMN IF NOT EXISTS role text NOT NULL DEFAULT 'user';

UPDATE gateway.users SET role = 'admin' WHERE is_admin = true AND role = 'user';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_role'
  ) THEN
    ALTER TABLE gateway.users
      ADD CONSTRAINT ck_users_role CHECK (role IN ('user', 'admin', 'support'));
  END IF;
END $$;

ALTER TABLE gateway.users DROP COLUMN IF EXISTS is_admin;

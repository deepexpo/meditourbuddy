-- Password reset: short-lived, single-use 6-digit codes emailed via Resend.
-- Only code_hash is stored, same reasoning as gateway.users.password_hash.
--
-- Safe to re-run.

CREATE TABLE IF NOT EXISTS gateway.password_reset_codes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES gateway.users(id) ON DELETE CASCADE,
  code_hash text NOT NULL,
  expires_at timestamptz NOT NULL,
  used_at timestamptz,
  attempt_count int NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_password_reset_codes_user_id_created_at
  ON gateway.password_reset_codes (user_id, created_at);

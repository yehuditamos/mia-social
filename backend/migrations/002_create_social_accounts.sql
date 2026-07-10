CREATE TABLE IF NOT EXISTS social_accounts (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id          UUID NOT NULL REFERENCES businesses(id),
  platform             TEXT NOT NULL,
  platform_account_id  TEXT NOT NULL,
  account_username     TEXT,
  account_display_name TEXT,
  page_id              TEXT,
  page_name            TEXT,
  access_token         TEXT NOT NULL,
  token_expires_at     TIMESTAMPTZ,
  refresh_required     BOOLEAN NOT NULL DEFAULT FALSE,
  status               TEXT NOT NULL DEFAULT 'active',
  metadata             JSONB,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(business_id, platform, platform_account_id)
);

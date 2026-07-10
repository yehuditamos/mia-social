CREATE TABLE IF NOT EXISTS auth_sessions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  state           TEXT UNIQUE NOT NULL,
  business_id     UUID NOT NULL REFERENCES businesses(id),
  initiated_by    UUID REFERENCES users(id),
  channel         TEXT NOT NULL DEFAULT 'whatsapp',
  channel_user_id TEXT NOT NULL,
  purpose         TEXT NOT NULL DEFAULT 'meta_connect',
  status          TEXT NOT NULL DEFAULT 'pending',
  expires_at      TIMESTAMPTZ NOT NULL,
  used_at         TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

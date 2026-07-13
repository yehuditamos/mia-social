CREATE TABLE IF NOT EXISTS reminders (
    id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id      UUID NOT NULL,
    phone_number TEXT NOT NULL,
    content      TEXT NOT NULL,
    remind_at    TIMESTAMPTZ NOT NULL,
    sent         BOOLEAN DEFAULT false,
    created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS reminders_remind_at_idx ON reminders (remind_at) WHERE sent = false;

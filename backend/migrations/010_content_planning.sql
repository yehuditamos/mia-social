ALTER TABLE businesses ADD COLUMN IF NOT EXISTS planning_day  INTEGER;
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS planning_time TEXT;

ALTER TABLE reminders ADD COLUMN IF NOT EXISTS recurrence     TEXT;
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS recurrence_day INTEGER;

CREATE TABLE IF NOT EXISTS content_ideas (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    business_id UUID NOT NULL,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    used        BOOLEAN DEFAULT false,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS content_plans (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    business_id UUID NOT NULL,
    month       TEXT NOT NULL,
    plan_text   TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);

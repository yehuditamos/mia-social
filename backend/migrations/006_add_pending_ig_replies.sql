CREATE TABLE IF NOT EXISTS pending_ig_replies (
    phone_number TEXT PRIMARY KEY,
    comment_id   TEXT NOT NULL,
    ig_user_id   TEXT NOT NULL,
    access_token TEXT NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS seen_ig_comments (
    comment_id TEXT PRIMARY KEY,
    ig_user_id TEXT NOT NULL,
    seen_at    TIMESTAMPTZ DEFAULT now()
);

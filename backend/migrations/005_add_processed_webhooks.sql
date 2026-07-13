CREATE TABLE IF NOT EXISTS processed_webhooks (
    message_id TEXT PRIMARY KEY,
    processed_at TIMESTAMPTZ DEFAULT now()
);

-- Clean up records older than 10 minutes automatically
CREATE INDEX IF NOT EXISTS idx_processed_webhooks_time
    ON processed_webhooks (processed_at);

-- Keep the most recently created row per user_id, delete the rest
DELETE FROM businesses
WHERE id NOT IN (
  SELECT DISTINCT ON (user_id) id
  FROM businesses
  ORDER BY user_id, created_at DESC
);

-- Add unique constraint so UPSERT works correctly
ALTER TABLE businesses ADD CONSTRAINT businesses_user_id_unique UNIQUE (user_id);

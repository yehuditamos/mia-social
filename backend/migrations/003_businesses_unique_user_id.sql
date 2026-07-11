-- Remove duplicate rows, keep the one with the most data (latest id)
DELETE FROM businesses
WHERE id NOT IN (
  SELECT MAX(id) FROM businesses GROUP BY user_id
);

-- Add unique constraint so UPSERT works correctly
ALTER TABLE businesses ADD CONSTRAINT businesses_user_id_unique UNIQUE (user_id);

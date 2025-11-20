-- Add claimed_news_rewards column to store which news article rewards users have claimed
-- This is a JSONB field that stores an array of claimed reward keys (e.g., ["news_0", "news_1"])

ALTER TABLE profile 
ADD COLUMN IF NOT EXISTS claimed_news_rewards JSONB DEFAULT '[]'::jsonb;

-- Add index for better performance when querying claimed rewards
CREATE INDEX IF NOT EXISTS idx_profile_claimed_news_rewards ON profile USING GIN (claimed_news_rewards);

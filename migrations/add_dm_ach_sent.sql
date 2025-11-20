-- Add dm_ach_sent column to track if DM achievement message was sent
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS dm_ach_sent INTEGER DEFAULT 0;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_user_dm_ach_sent ON "user" (dm_ach_sent);

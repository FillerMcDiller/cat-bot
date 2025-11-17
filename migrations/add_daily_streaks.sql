-- Add daily streak tracking to profile table
ALTER TABLE public.profile 
ADD COLUMN last_daily_claim BIGINT DEFAULT 0,
ADD COLUMN daily_streak INTEGER DEFAULT 0;

-- Add index for efficient queries
CREATE INDEX idx_profile_last_daily ON public.profile USING btree (last_daily_claim);

-- Add columns for tracking breeding and battle wins
ALTER TABLE public.profile 
ADD COLUMN IF NOT EXISTS breeds_total integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS battles_won integer DEFAULT 0;

-- Add indexes for leaderboard performance
CREATE INDEX IF NOT EXISTS idx_profile_breeds_total ON public.profile USING btree (breeds_total);
CREATE INDEX IF NOT EXISTS idx_profile_battles_won ON public.profile USING btree (battles_won);

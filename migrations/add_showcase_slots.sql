-- Add showcase slots to profile table (default 2: best achievement + best cat)
ALTER TABLE public.profile 
ADD COLUMN showcase_slots INTEGER DEFAULT 2;

-- Add index for efficient queries
CREATE INDEX idx_profile_showcase_slots ON public.profile USING btree (showcase_slots);

-- Add cat_instances JSONB column to store cat instances directly in the database
-- This prevents data loss when moving servers

ALTER TABLE public.profile 
ADD COLUMN IF NOT EXISTS cat_instances JSONB DEFAULT '[]'::jsonb;

-- Create an index for faster queries
CREATE INDEX IF NOT EXISTS idx_profile_cat_instances ON public.profile USING gin (cat_instances);

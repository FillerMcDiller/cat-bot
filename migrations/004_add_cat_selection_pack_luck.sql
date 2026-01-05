-- Migration 004: Add cat selection and pack luck settings
-- Adds disabled_cats and pack_luck_multiplier to channel table

-- Add disabled_cats column (comma-separated list of cat types to not spawn)
ALTER TABLE public.channel 
ADD COLUMN IF NOT EXISTS disabled_cats text DEFAULT '';

-- Add pack_luck_multiplier column (multiplier for pack openings, default 1.0)
ALTER TABLE public.channel 
ADD COLUMN IF NOT EXISTS pack_luck_multiplier double precision DEFAULT 1.0;

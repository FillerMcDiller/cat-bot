-- Migration 003: Add channel race and spawn settings
-- Adds race_channel_id, race_frequency, and spawn_luck_multiplier to channel table

-- Add race_channel_id column (nullable, points to channel_id where races are enabled)
ALTER TABLE public.channel 
ADD COLUMN IF NOT EXISTS race_channel_id bigint DEFAULT NULL;

-- Add race_frequency column (in seconds, default 600 = 10 minutes)
ALTER TABLE public.channel 
ADD COLUMN IF NOT EXISTS race_frequency bigint DEFAULT 600;

-- Add spawn_luck_multiplier column (multiplier for enchanted spawns, default 1.0)
ALTER TABLE public.channel 
ADD COLUMN IF NOT EXISTS spawn_luck_multiplier double precision DEFAULT 1.0;

-- Note: spawn_times_min and spawn_times_max already exist in the schema

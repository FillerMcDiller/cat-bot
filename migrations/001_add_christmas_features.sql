-- ============================================================================
-- Migration: Add Christmas Event Features
-- Date: 2025-11-28
-- Description: Adds all database columns for Christmas advent, naughty/nice 
--              scoring, tree decorations, and achievements
-- ============================================================================

-- Add Christmas event tracking to profile table
ALTER TABLE public.profile 
ADD COLUMN IF NOT EXISTS advent_claimed TEXT DEFAULT '',  -- Comma-separated days claimed (e.g. "1,2,3")
ADD COLUMN IF NOT EXISTS advent_last_claim BIGINT DEFAULT 0,
ADD COLUMN IF NOT EXISTS naughty_score INTEGER DEFAULT 0,  -- Increases with stealing, etc.
ADD COLUMN IF NOT EXISTS nice_score INTEGER DEFAULT 0,  -- Increases with gifting, helping
ADD COLUMN IF NOT EXISTS santa_banned BOOLEAN DEFAULT false,  -- If true, no advent rewards
ADD COLUMN IF NOT EXISTS pack_festive INTEGER DEFAULT 0;

-- Add Christmas achievements
ALTER TABLE public.profile
ADD COLUMN IF NOT EXISTS christmas_spirit BOOLEAN DEFAULT false,  -- Catch 25 festive cats
ADD COLUMN IF NOT EXISTS advent_master BOOLEAN DEFAULT false,  -- Claim all 25 days
ADD COLUMN IF NOT EXISTS gift_giver BOOLEAN DEFAULT false,  -- Gift 10 cats during December
ADD COLUMN IF NOT EXISTS nice_list BOOLEAN DEFAULT false,  -- Maintain nice_score > naughty_score
ADD COLUMN IF NOT EXISTS naughty_list BOOLEAN DEFAULT false,  -- Get banned by Santa
ADD COLUMN IF NOT EXISTS festive_collector BOOLEAN DEFAULT false,  -- Open 50 festive packs
ADD COLUMN IF NOT EXISTS tree_decorated BOOLEAN DEFAULT false;  -- Completed the Christmas tree

-- Add Christmas tree decoration tracking
ALTER TABLE public.profile
ADD COLUMN IF NOT EXISTS tree_ornaments TEXT DEFAULT '',  -- Comma-separated ornament IDs (e.g. "1,3,5")
ADD COLUMN IF NOT EXISTS tree_ornament_count INTEGER DEFAULT 0,  -- Number of ornaments collected (0-8)
ADD COLUMN IF NOT EXISTS christmas_spirit_progress INTEGER DEFAULT 0,  -- Track festive cats caught
ADD COLUMN IF NOT EXISTS gift_giver_progress INTEGER DEFAULT 0,  -- Track gifts given
ADD COLUMN IF NOT EXISTS pack_festive_opened INTEGER DEFAULT 0,  -- Track festive packs opened
ADD COLUMN IF NOT EXISTS winter_battles INTEGER DEFAULT 0,  -- Track winter-themed battles
ADD COLUMN IF NOT EXISTS team_battle_wins INTEGER DEFAULT 0;  -- Track team battle wins

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_profile_advent ON public.profile USING btree (advent_last_claim);
CREATE INDEX IF NOT EXISTS idx_profile_naughty_nice ON public.profile USING btree (naughty_score, nice_score);

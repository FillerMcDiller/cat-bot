-- Add cosmetics system: owned cosmetics, equipped cosmetics, and cosmetic shop
ALTER TABLE public.profile 
ADD COLUMN IF NOT EXISTS owned_cosmetics TEXT DEFAULT '',
ADD COLUMN IF NOT EXISTS equipped_badge TEXT DEFAULT '',
ADD COLUMN IF NOT EXISTS equipped_title TEXT DEFAULT '',
ADD COLUMN IF NOT EXISTS equipped_color TEXT DEFAULT '',
ADD COLUMN IF NOT EXISTS equipped_effect TEXT DEFAULT '';

-- Cosmetics use existing kibble currency (no new column needed)

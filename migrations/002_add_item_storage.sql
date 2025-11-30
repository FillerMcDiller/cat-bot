-- ============================================================================
-- Migration: Add Item Storage Table
-- Date: 2025-11-30
-- Description: Migrates item tracking from JSON file storage to database
-- ============================================================================

-- Create the item table for storing user items
CREATE TABLE IF NOT EXISTS public.item (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    item_key VARCHAR(50) NOT NULL,  -- Format: "item_code_TIER" (e.g., "candy_cane_I")
    quantity INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(guild_id, user_id, item_key)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_item_guild_user ON public.item USING btree (guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_item_key ON public.item USING btree (item_key);

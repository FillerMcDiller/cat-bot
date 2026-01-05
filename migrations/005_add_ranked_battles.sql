-- Add ranked battle system columns to profile table
ALTER TABLE profile
ADD COLUMN IF NOT EXISTS ranked_rating integer DEFAULT 1000,
ADD COLUMN IF NOT EXISTS ranked_wins integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS ranked_losses integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS ranked_season integer DEFAULT 1,
ADD COLUMN IF NOT EXISTS ranked_peak_rating integer DEFAULT 1000,
ADD COLUMN IF NOT EXISTS ranked_rewards_claimed boolean DEFAULT false;

-- Create index for ranked leaderboard queries
CREATE INDEX IF NOT EXISTS idx_profile_ranked_rating ON profile USING btree (ranked_rating DESC, ranked_wins DESC);

-- Create table to track ranked seasons
CREATE TABLE IF NOT EXISTS ranked_season (
    season_number integer PRIMARY KEY,
    start_time bigint NOT NULL,
    end_time bigint NOT NULL,
    active boolean DEFAULT true
);

-- Create table to track season rewards
CREATE TABLE IF NOT EXISTS ranked_rewards (
    id SERIAL PRIMARY KEY,
    user_id bigint NOT NULL,
    guild_id bigint NOT NULL,
    season integer NOT NULL,
    final_rank integer NOT NULL,
    final_rating integer NOT NULL,
    kibble_reward integer DEFAULT 0,
    packs_reward text DEFAULT '',
    title_reward text DEFAULT '',
    claimed boolean DEFAULT false,
    UNIQUE(user_id, guild_id, season)
);

CREATE INDEX IF NOT EXISTS idx_ranked_rewards_user ON ranked_rewards USING btree (user_id, season);
CREATE INDEX IF NOT EXISTS idx_ranked_rewards_season ON ranked_rewards USING btree (season, final_rank);

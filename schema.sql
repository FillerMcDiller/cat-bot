SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

ALTER SCHEMA public OWNER TO cat_bot;
COMMENT ON SCHEMA public IS '';


SET default_tablespace = '';

SET default_table_access_method = heap;

CREATE TABLE IF NOT EXISTS public.channel (
    channel_id bigint NOT NULL,
    cat bigint DEFAULT 0,
    spawn_times_min bigint DEFAULT 120,
    spawn_times_max bigint DEFAULT 1200,
    lastcatches bigint DEFAULT 0,
    yet_to_spawn bigint DEFAULT 0,
    appear character varying(4000) DEFAULT ''::character varying,
    cought character varying(4000) DEFAULT ''::character varying,
    webhook character varying(255) DEFAULT ''::character varying,
    forcespawned boolean DEFAULT false,
    cattype character varying(20) DEFAULT ''::character varying,
    cat_rains bigint DEFAULT 0,
    enchanted boolean DEFAULT false
);


ALTER TABLE public.channel OWNER TO cat_bot;


CREATE TABLE IF NOT EXISTS public.prism (
    id integer NOT NULL,
    user_id bigint NOT NULL,
    guild_id bigint NOT NULL,
    "time" bigint NOT NULL,
    creator bigint NOT NULL,
    name character varying(20) NOT NULL,
    catches_boosted integer DEFAULT 0
);


ALTER TABLE public.prism OWNER TO cat_bot;

CREATE SEQUENCE IF NOT EXISTS public.prism_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.prism_id_seq OWNER TO cat_bot;


ALTER SEQUENCE public.prism_id_seq OWNED BY public.prism.id;


CREATE TABLE IF NOT EXISTS public.profile (
    id integer NOT NULL,
    user_id bigint NOT NULL,
    guild_id bigint NOT NULL,
    "time" real DEFAULT 99999999999999,
    timeslow real DEFAULT 0,
    timeout bigint DEFAULT 0,
    cataine_active bigint DEFAULT 0,
    battlepass smallint DEFAULT 0,
    progress smallint DEFAULT 0,
    dark_market_level smallint DEFAULT 0,
    dark_market_active boolean DEFAULT false,
    story_complete boolean DEFAULT false,
    cataine_week smallint DEFAULT 0,
    recent_week smallint DEFAULT 0,
    funny integer DEFAULT 0,
    facts integer DEFAULT 0,
    gambles smallint DEFAULT 0,
    "cat_Fine" integer DEFAULT 0,
    "cat_Nice" integer DEFAULT 0,
    "cat_Good" integer DEFAULT 0,
    "cat_Rare" integer DEFAULT 0,
    "cat_Wild" integer DEFAULT 0,
    "cat_Baby" integer DEFAULT 0,
    "cat_Epic" integer DEFAULT 0,
    "cat_Sus" integer DEFAULT 0,
    "cat_Brave" integer DEFAULT 0,
    "cat_Rickroll" integer DEFAULT 0,
    "cat_Reverse" integer DEFAULT 0,
    "cat_Superior" integer DEFAULT 0,
    "cat_Trash" integer DEFAULT 0,
    "cat_Legendary" integer DEFAULT 0,
    "cat_Mythic" integer DEFAULT 0,
    cat_8bit integer DEFAULT 0,
    "cat_Corrupt" integer DEFAULT 0,
    "cat_Professor" integer DEFAULT 0,
    "cat_Divine" integer DEFAULT 0,
    "cat_Real" integer DEFAULT 0,
    "cat_Zombie" integer DEFAULT 0,
    "cat_Ultimate" integer DEFAULT 0,
    "cat_eGirl" integer DEFAULT 0,
	"cat_Fire" integer DEFAULT 0,
    "cat_Donut" integer DEFAULT 0,
	"cat_TV" integer DEFAULT 0,
	"cat_Candy" integer DEFAULT 0,
	"cat_Chef" integer DEFAULT 0,
	"cat_Alien" integer DEFAULT 0,
    "cat_Water" integer DEFAULT 0,
    "cat_Jamming" integer DEFAULT 0,
    "cat_Santa" integer DEFAULT 0,
    "cat_Elf" integer DEFAULT 0,
    "cat_Snowman" integer DEFAULT 0,
    "cat_ChristmasTree" integer DEFAULT 0,
    "cat_Gingerbread" integer DEFAULT 0,
    "cat_Cocoa" integer DEFAULT 0,
    "cat_Present" integer DEFAULT 0,
    first boolean DEFAULT false,
    second boolean DEFAULT false,
    third boolean DEFAULT false,
    fourth boolean DEFAULT false,
    donator boolean DEFAULT false,
    anti_donator boolean DEFAULT false,
    extrovert boolean DEFAULT false,
    fast_catcher boolean DEFAULT false,
    slow_catcher boolean DEFAULT false,
    collecter boolean DEFAULT false,
    trolled boolean DEFAULT false,
    achiever boolean DEFAULT false,
    leader boolean DEFAULT false,
    dark_market boolean DEFAULT false,
    randomizer boolean DEFAULT false,
    pineapple boolean DEFAULT false,
    daily boolean DEFAULT false,
    dm boolean DEFAULT false,
    who_ping boolean DEFAULT false,
    introvert boolean DEFAULT false,
    pleasedonotthecat boolean DEFAULT false,
    pleasedothecat boolean DEFAULT false,
    worship boolean DEFAULT false,
    test_ach boolean DEFAULT false,
    "4k" boolean DEFAULT false,
    curious boolean DEFAULT false,
    car boolean DEFAULT false,
    "???" boolean DEFAULT false,
    not_quite boolean DEFAULT false,
    website_user boolean DEFAULT false,
    coffee boolean DEFAULT false,
    sussy boolean DEFAULT false,
    egril boolean DEFAULT false,
    bwomp boolean DEFAULT false,
    silly boolean DEFAULT false,
    nice boolean DEFAULT false,
    click_here boolean DEFAULT false,
    patient_reader boolean DEFAULT false,
    nerd boolean DEFAULT false,
    loud_cat boolean DEFAULT false,
    reverse boolean DEFAULT false,
    desperate boolean DEFAULT false,
    lonely boolean DEFAULT false,
    "8k" boolean DEFAULT false,
    scammed boolean DEFAULT false,
    absolutely_nothing boolean DEFAULT false,
    sacrifice boolean DEFAULT false,
    not_like_that boolean DEFAULT false,
    gambling_one boolean DEFAULT false,
    broke boolean DEFAULT false,
    secret boolean DEFAULT false,
    good_citizen boolean DEFAULT false,
    perfectly_balanced boolean DEFAULT false,
    fact_enjoyer boolean DEFAULT false,
    morse_cat boolean DEFAULT false,
    lucky boolean DEFAULT false,
    gambling_two boolean DEFAULT false,
    nerd_battle boolean DEFAULT false,
    its_not_working boolean DEFAULT false,
    rich boolean DEFAULT false,
    pie boolean DEFAULT false,
    perfection boolean DEFAULT false,
    all_the_same boolean DEFAULT false,
    paradoxical_gambler boolean DEFAULT false,
    darkest_market boolean DEFAULT false,
    capitalism boolean DEFAULT false,
    profit boolean DEFAULT false,
    catn boolean DEFAULT false,
    coupon_user boolean DEFAULT false,
    dataminer boolean DEFAULT false,
    blackhole boolean DEFAULT false,
    cat_rain boolean DEFAULT false,
    thanksforplaying boolean DEFAULT false,
    prisms_unlocked boolean DEFAULT false,
    boosted boolean DEFAULT false,
    news boolean DEFAULT false,
    reminder boolean DEFAULT false,
    prism boolean DEFAULT false,
    balling boolean DEFAULT false,
    slots boolean DEFAULT false,
    win_slots boolean DEFAULT false,
    big_win_slots boolean DEFAULT false,
    slot_spins integer DEFAULT 0,
    slot_wins integer DEFAULT 0,
    slot_big_wins smallint DEFAULT 0,
    finale_seen boolean DEFAULT false,
    rain_minutes smallint DEFAULT 0,
    season smallint DEFAULT 0,
    vote_reward smallint DEFAULT 0,
    vote_cooldown bigint DEFAULT 1,
    catch_quest character varying(30) DEFAULT ''::character varying,
    catch_progress smallint DEFAULT 0,
    catch_cooldown bigint DEFAULT 1,
    catch_reward smallint DEFAULT 0,
    misc_quest character varying(30) DEFAULT ''::character varying,
    misc_progress smallint DEFAULT 0,
    misc_cooldown bigint DEFAULT 1,
    misc_reward smallint DEFAULT 0,
    extra_quest character varying(30) DEFAULT ''::character varying,
    extra_progress smallint DEFAULT 0,
    extra_cooldown bigint DEFAULT 1,
    extra_reward smallint DEFAULT 0,
    reminder_catch bigint DEFAULT 0,
    reminder_extra bigint DEFAULT 0,
    reminder_misc bigint DEFAULT 0,
    reminders_enabled boolean DEFAULT false,
    multilingual boolean DEFAULT false,
    debt boolean DEFAULT false,
    debt_seen boolean DEFAULT false,
    bp_history character varying DEFAULT ''::character varying,
    boosted_catches integer DEFAULT 0,
    cataine_activations integer DEFAULT 0,
    cataine_bought integer DEFAULT 0,
    quests_completed integer DEFAULT 0,
    total_catches integer DEFAULT 0,
    total_catch_time bigint DEFAULT 0,
    perfection_count integer DEFAULT 0,
    rain_participations integer DEFAULT 0,
    rain_minutes_started integer DEFAULT 0,
    reminders_set integer DEFAULT 0,
    cats_gifted integer DEFAULT 0,
    cat_gifts_recieved integer DEFAULT 0,
    trades_completed integer DEFAULT 0,
    cats_traded integer DEFAULT 0,
    new_user boolean DEFAULT true,
    ttt_played integer DEFAULT 0,
    ttt_won integer DEFAULT 0,
    ttt_draws integer DEFAULT 0,
    ttt_win boolean DEFAULT false,
    packs_opened integer DEFAULT 0,
    pack_upgrades integer DEFAULT 0,
    pack_wooden integer DEFAULT 0,
    pack_stone integer DEFAULT 0,
    pack_bronze integer DEFAULT 0,
    pack_silver integer DEFAULT 0,
    pack_gold integer DEFAULT 0,
    pack_platinum integer DEFAULT 0,
    pack_diamond integer DEFAULT 0,
    pack_celestial integer DEFAULT 0,
    pack_festive integer DEFAULT 0,
    highlighted_stat character varying(30) DEFAULT 'time_records'::character varying,
    puzzle_pieces integer DEFAULT 0,
    cookies bigint DEFAULT 0,
    kibble bigint DEFAULT 0,
    cookieclicker boolean DEFAULT false,
    cookiesclicked boolean DEFAULT false,
    event_rain_points integer DEFAULT 0,
    best_pig_score integer DEFAULT 0,
    pig50 boolean default false,
    pig100 boolean default false,
    last_steal bigint DEFAULT 0,
    showcase_slots INTEGER DEFAULT 2,
    huzzful boolean DEFAULT false,
    freak boolean DEFAULT false,
    full_stack boolean DEFAULT false,
    unfunny boolean DEFAULT false,
    genetically_gifted boolean DEFAULT false,
    you_failure boolean DEFAULT false,
    grinder boolean DEFAULT false,
    owned_cosmetics TEXT DEFAULT '',
    equipped_badge TEXT DEFAULT '',
    equipped_title TEXT DEFAULT '',
    equipped_color TEXT DEFAULT '',
    equipped_effect TEXT DEFAULT '',
    claimed_news_rewards JSONB DEFAULT '[]'::jsonb,
    cat_instances JSONB DEFAULT '[]'::jsonb,
    breeds_total integer DEFAULT 0,
    battles_won integer DEFAULT 0,
    last_daily_claim BIGINT DEFAULT 0,
    daily_streak INTEGER DEFAULT 0
);


ALTER TABLE public.profile OWNER TO cat_bot;

CREATE SEQUENCE IF NOT EXISTS public.profile_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.profile_id_seq OWNER TO cat_bot;

ALTER SEQUENCE public.profile_id_seq OWNED BY public.profile.id;

CREATE TABLE IF NOT EXISTS public.reminder (
    id integer NOT NULL,
    user_id bigint NOT NULL,
    "time" bigint NOT NULL,
    text character varying(2000) NOT NULL
);


ALTER TABLE public.reminder OWNER TO cat_bot;

CREATE SEQUENCE IF NOT EXISTS public.reminder_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.reminder_id_seq OWNER TO cat_bot;

ALTER SEQUENCE public.reminder_id_seq OWNED BY public.reminder.id;

CREATE TABLE IF NOT EXISTS public.adventure (
    id integer NOT NULL,
    user_id bigint NOT NULL,
    guild_id bigint NOT NULL,
    cat_type character varying(50) NOT NULL,
    cat_id character varying(255),
    start_time bigint NOT NULL,
    end_time bigint NOT NULL,
    adventure_type character varying(50) NOT NULL
);

ALTER TABLE public.adventure OWNER TO cat_bot;

CREATE SEQUENCE IF NOT EXISTS public.adventure_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER TABLE public.adventure_id_seq OWNER TO cat_bot;

ALTER SEQUENCE public.adventure_id_seq OWNED BY public.adventure.id;

CREATE TABLE IF NOT EXISTS public.deck (
    id integer NOT NULL,
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    deck_data JSONB NOT NULL
);

ALTER TABLE public.deck OWNER TO cat_bot;

CREATE SEQUENCE IF NOT EXISTS public.deck_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER TABLE public.deck_id_seq OWNER TO cat_bot;

ALTER SEQUENCE public.deck_id_seq OWNED BY public.deck.id;

CREATE TABLE IF NOT EXISTS public."user" (
    user_id bigint NOT NULL,
    vote_time_topgg bigint DEFAULT 0,
    custom character varying(255) DEFAULT ''::character varying,
    emoji character varying(255) DEFAULT ''::character varying,
    color character varying(255) DEFAULT ''::character varying,
    image character varying(255) DEFAULT ''::character varying,
    premium boolean DEFAULT false,
    claimed_free_rain boolean DEFAULT false,
    rain_minutes smallint DEFAULT 0,
    news_state character(2000) DEFAULT ''::bpchar,
    reminder_vote bigint DEFAULT 0,
    custom_num integer DEFAULT 1,
    total_votes integer DEFAULT 0,
    vote_streak integer DEFAULT 0,
    max_vote_streak integer DEFAULT 0,
    streak_freezes integer DEFAULT 0,
    cats_blessed bigint DEFAULT 0,
    blessings_enabled boolean DEFAULT false,
    blessings_anonymous boolean DEFAULT false,
    dm_ach_sent INTEGER DEFAULT 0
);


ALTER TABLE public."user" OWNER TO cat_bot;

ALTER TABLE ONLY public.prism ALTER COLUMN id SET DEFAULT nextval('public.prism_id_seq'::regclass);

ALTER TABLE ONLY public.profile ALTER COLUMN id SET DEFAULT nextval('public.profile_id_seq'::regclass);

ALTER TABLE ONLY public.reminder ALTER COLUMN id SET DEFAULT nextval('public.reminder_id_seq'::regclass);

ALTER TABLE ONLY public.adventure ALTER COLUMN id SET DEFAULT nextval('public.adventure_id_seq'::regclass);

ALTER TABLE ONLY public.deck ALTER COLUMN id SET DEFAULT nextval('public.deck_id_seq'::regclass);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'channel_pkey') THEN
        ALTER TABLE ONLY public.channel ADD CONSTRAINT channel_pkey PRIMARY KEY (channel_id);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'prism_pkey') THEN
        ALTER TABLE ONLY public.prism ADD CONSTRAINT prism_pkey PRIMARY KEY (id);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'profile_pkey') THEN
        ALTER TABLE ONLY public.profile ADD CONSTRAINT profile_pkey PRIMARY KEY (id);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'reminder_pkey') THEN
        ALTER TABLE ONLY public.reminder ADD CONSTRAINT reminder_pkey PRIMARY KEY (id);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'adventure_pkey') THEN
        ALTER TABLE ONLY public.adventure ADD CONSTRAINT adventure_pkey PRIMARY KEY (id);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'deck_pkey') THEN
        ALTER TABLE ONLY public.deck ADD CONSTRAINT deck_pkey PRIMARY KEY (id);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_pkey') THEN
        ALTER TABLE ONLY public."user" ADD CONSTRAINT user_pkey PRIMARY KEY (user_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_guild_id ON public.profile USING btree (guild_id);

CREATE INDEX IF NOT EXISTS idx_prism_guild_i_2a2071 ON public.prism USING btree (guild_id);


CREATE INDEX IF NOT EXISTS idx_prism_user_id_bfacf7 ON public.prism USING btree (user_id, guild_id);


CREATE INDEX IF NOT EXISTS idx_profile_guild_i_ae5642 ON public.profile USING btree (guild_id);


CREATE INDEX IF NOT EXISTS idx_profile_user_id_c9cc1c ON public.profile USING btree (user_id, guild_id);


CREATE INDEX IF NOT EXISTS idx_reminder_time_b3a9a4 ON public.reminder USING btree ("time");


CREATE INDEX IF NOT EXISTS prism_guild_id ON public.prism USING btree (guild_id);

CREATE INDEX IF NOT EXISTS prism_user_id_guild_id ON public.prism USING btree (user_id, guild_id);

CREATE UNIQUE INDEX IF NOT EXISTS profile_user_id_guild_id ON public.profile USING btree (user_id, guild_id);

CREATE INDEX IF NOT EXISTS reminder_time ON public.reminder USING btree ("time");

CREATE INDEX IF NOT EXISTS idx_user_dm_ach_sent ON public."user" (dm_ach_sent);

CREATE INDEX IF NOT EXISTS idx_profile_showcase_slots ON public.profile USING btree (showcase_slots);

CREATE INDEX IF NOT EXISTS idx_profile_claimed_news_rewards ON public.profile USING GIN (claimed_news_rewards);

CREATE INDEX IF NOT EXISTS idx_profile_cat_instances ON public.profile USING gin (cat_instances);

CREATE INDEX IF NOT EXISTS idx_profile_breeds_total ON public.profile USING btree (breeds_total);

CREATE INDEX IF NOT EXISTS idx_profile_battles_won ON public.profile USING btree (battles_won);

CREATE INDEX IF NOT EXISTS idx_profile_last_daily ON public.profile USING btree (last_daily_claim);

CREATE INDEX IF NOT EXISTS idx_adventure_user_id ON public.adventure USING btree (user_id);

CREATE INDEX IF NOT EXISTS idx_adventure_end_time ON public.adventure USING btree (end_time);

CREATE UNIQUE INDEX IF NOT EXISTS deck_guild_user ON public.deck USING btree (guild_id, user_id);

-- Add missing columns if they don't exist (comprehensive safety check)
ALTER TABLE public.profile
ADD COLUMN IF NOT EXISTS "time" real DEFAULT 99999999999999,
ADD COLUMN IF NOT EXISTS timeslow real DEFAULT 0,
ADD COLUMN IF NOT EXISTS timeout bigint DEFAULT 0,
ADD COLUMN IF NOT EXISTS cataine_active bigint DEFAULT 0,
ADD COLUMN IF NOT EXISTS battlepass smallint DEFAULT 0,
ADD COLUMN IF NOT EXISTS progress smallint DEFAULT 0,
ADD COLUMN IF NOT EXISTS dark_market_level smallint DEFAULT 0,
ADD COLUMN IF NOT EXISTS dark_market_active boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS story_complete boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS cataine_week smallint DEFAULT 0,
ADD COLUMN IF NOT EXISTS recent_week smallint DEFAULT 0,
ADD COLUMN IF NOT EXISTS funny integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS facts integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS gambles smallint DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Fine" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Nice" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Good" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Rare" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Wild" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Baby" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Epic" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Sus" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Brave" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Rickroll" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Reverse" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Superior" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Trash" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Legendary" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Mythic" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS cat_8bit integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Corrupt" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Professor" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Divine" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Real" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Zombie" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Ultimate" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_eGirl" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Fire" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Donut" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_TV" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Candy" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Chef" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Alien" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Water" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Jamming" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Santa" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Elf" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Snowman" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_ChristmasTree" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Gingerbread" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Cocoa" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS "cat_Present" integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS first boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS second boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS third boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS fourth boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS donator boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS anti_donator boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS extrovert boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS fast_catcher boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS slow_catcher boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS collecter boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS trolled boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS achiever boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS leader boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS dark_market boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS randomizer boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS pineapple boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS daily boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS dm boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS who_ping boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS introvert boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS pleasedonotthecat boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS pleasedothecat boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS worship boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS test_ach boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS "4k" boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS curious boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS car boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS "???" boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS not_quite boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS website_user boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS coffee boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS sussy boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS egril boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS bwomp boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS silly boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS nice boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS click_here boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS patient_reader boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS nerd boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS loud_cat boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS reverse boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS desperate boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS lonely boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS "8k" boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS scammed boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS absolutely_nothing boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS sacrifice boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS not_like_that boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS gambling_one boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS broke boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS secret boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS good_citizen boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS perfectly_balanced boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS fact_enjoyer boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS morse_cat boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS joober boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS cst boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS cab boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS ttt_win boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS lucky boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS gambling_two boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS nerd_battle boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS its_not_working boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS rich boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS pie boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS perfection boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS all_the_same boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS paradoxical_gambler boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS darkest_market boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS capitalism boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS profit boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS prism boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS catn boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS coupon_user boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS dataminer boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS blackhole boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS cat_rain boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS thanksforplaying boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS prisms_unlocked boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS boosted boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS news boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS reminder boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS balling boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS slots boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS win_slots boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS big_win_slots boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS slot_spins integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS slot_wins integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS slot_big_wins smallint DEFAULT 0,
ADD COLUMN IF NOT EXISTS finale_seen boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS rain_minutes smallint DEFAULT 0,
ADD COLUMN IF NOT EXISTS season smallint DEFAULT 0,
ADD COLUMN IF NOT EXISTS vote_reward smallint DEFAULT 0,
ADD COLUMN IF NOT EXISTS vote_cooldown bigint DEFAULT 1,
ADD COLUMN IF NOT EXISTS catch_quest character varying(30) DEFAULT ''::character varying,
ADD COLUMN IF NOT EXISTS catch_progress smallint DEFAULT 0,
ADD COLUMN IF NOT EXISTS catch_cooldown bigint DEFAULT 1,
ADD COLUMN IF NOT EXISTS catch_reward smallint DEFAULT 0,
ADD COLUMN IF NOT EXISTS misc_quest character varying(30) DEFAULT ''::character varying,
ADD COLUMN IF NOT EXISTS misc_progress smallint DEFAULT 0,
ADD COLUMN IF NOT EXISTS misc_cooldown bigint DEFAULT 1,
ADD COLUMN IF NOT EXISTS misc_reward smallint DEFAULT 0,
ADD COLUMN IF NOT EXISTS extra_quest character varying(30) DEFAULT ''::character varying,
ADD COLUMN IF NOT EXISTS extra_progress smallint DEFAULT 0,
ADD COLUMN IF NOT EXISTS extra_cooldown bigint DEFAULT 1,
ADD COLUMN IF NOT EXISTS extra_reward smallint DEFAULT 0,
ADD COLUMN IF NOT EXISTS reminder_catch bigint DEFAULT 0,
ADD COLUMN IF NOT EXISTS reminder_extra bigint DEFAULT 0,
ADD COLUMN IF NOT EXISTS reminder_misc bigint DEFAULT 0,
ADD COLUMN IF NOT EXISTS reminders_enabled boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS multilingual boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS debt boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS debt_seen boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS bp_history character varying DEFAULT ''::character varying,
ADD COLUMN IF NOT EXISTS boosted_catches integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS cataine_activations integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS cataine_bought integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS quests_completed integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_catches integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_catch_time bigint DEFAULT 0,
ADD COLUMN IF NOT EXISTS perfection_count integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS rain_participations integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS rain_minutes_started integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS reminders_set integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS cats_gifted integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS cat_gifts_recieved integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS trades_completed integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS cats_traded integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS new_user boolean DEFAULT true,
ADD COLUMN IF NOT EXISTS ttt_played integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS ttt_won integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS ttt_draws integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS packs_opened integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS pack_upgrades integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS pack_wooden integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS pack_stone integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS pack_bronze integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS pack_silver integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS pack_gold integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS pack_platinum integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS pack_diamond integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS pack_celestial integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS pack_festive integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS highlighted_stat character varying(30) DEFAULT 'time_records'::character varying,
ADD COLUMN IF NOT EXISTS puzzle_pieces integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS cookies bigint DEFAULT 0,
ADD COLUMN IF NOT EXISTS kibble bigint DEFAULT 0,
ADD COLUMN IF NOT EXISTS cookieclicker boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS cookiesclicked boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS event_rain_points integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS best_pig_score integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS pig50 boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS pig100 boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS last_steal bigint DEFAULT 0,
ADD COLUMN IF NOT EXISTS showcase_slots INTEGER DEFAULT 2,
ADD COLUMN IF NOT EXISTS huzzful boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS freak boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS full_stack boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS unfunny boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS genetically_gifted boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS you_failure boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS grinder boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS owned_cosmetics TEXT DEFAULT '',
ADD COLUMN IF NOT EXISTS equipped_badge TEXT DEFAULT '',
ADD COLUMN IF NOT EXISTS equipped_title TEXT DEFAULT '',
ADD COLUMN IF NOT EXISTS equipped_color TEXT DEFAULT '',
ADD COLUMN IF NOT EXISTS equipped_effect TEXT DEFAULT '',
ADD COLUMN IF NOT EXISTS claimed_news_rewards JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS cat_instances JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS breeds_total integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS battles_won integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_daily_claim BIGINT DEFAULT 0,
ADD COLUMN IF NOT EXISTS daily_streak INTEGER DEFAULT 0;

REVOKE USAGE ON SCHEMA public FROM PUBLIC;

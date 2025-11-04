-- Add new achievement columns to profile table
ALTER TABLE public.profile
    ADD COLUMN huzzful boolean DEFAULT false,
    ADD COLUMN freak boolean DEFAULT false,
    ADD COLUMN full_stack boolean DEFAULT false,
    ADD COLUMN unfunny boolean DEFAULT false,
    ADD COLUMN genetically_gifted boolean DEFAULT false,
    ADD COLUMN you_failure boolean DEFAULT false,
    ADD COLUMN grinder boolean DEFAULT false;
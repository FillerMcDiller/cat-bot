-- Migration: add cat_Zombie column to profile table
ALTER TABLE public.profile
    ADD COLUMN "cat_Zombie" integer DEFAULT 0;

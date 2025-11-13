-- Migration: add kibble column to profile for per-server Kibble currency
ALTER TABLE public.profile ADD COLUMN kibble bigint DEFAULT 0;

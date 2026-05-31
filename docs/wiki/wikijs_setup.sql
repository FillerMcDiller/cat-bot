-- Wiki.js quick PostgreSQL setup script
-- Usage: run this as a superuser (e.g. the 'postgres' user) with psql:
--   psql -h <HOST> -U postgres -f wikijs_setup.sql
-- Replace the default password below before running in production.

BEGIN;

-- 1) Create a dedicated role/user for Wiki.js
CREATE USER wikijs WITH PASSWORD 'changeme';

-- 2) Create the wiki database and set the owner
CREATE DATABASE wikijs OWNER wikijs;

-- 3) Connect to the new database (psql meta-command; OK when run with psql)
\connect wikijs

-- 4) Recommended extensions for full-text/search features
-- NOTE: creating extensions requires superuser privileges on the cluster.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 5) Create a dedicated schema (optional) and set search_path for the role
CREATE SCHEMA IF NOT EXISTS wikijs AUTHORIZATION wikijs;
ALTER ROLE wikijs SET search_path = wikijs, public;

COMMIT;

-- Post-run checklist:
-- - Change the password for `wikijs` in this file before applying to production.
-- - If you are running this on a managed DB where you cannot create extensions, ask your admin to enable the listed extensions.
-- - Use the connection values in your Wiki.js `.env` (DB_HOST, DB_PORT, DB_USER=wikijs, DB_PASS, DB_NAME=wikijs).

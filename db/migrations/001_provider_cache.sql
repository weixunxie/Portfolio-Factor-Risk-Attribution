-- 001_provider_cache.sql
--
-- Persistent key/value cache for external provider responses
-- (Alpha Vantage JSON payloads and per-ticker price series).
--
-- Why: Railway's container filesystem is ephemeral — the file cache under
-- data/cache/ is wiped on every restart/redeploy, so any ticker that is not in
-- data/processed/returns.csv had to be re-fetched from the network on a cold
-- container. This table moves that cache into Postgres so it survives restarts.
--
-- How to apply: paste this file into the Supabase SQL Editor and run it once.
-- Safe to re-run (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS provider_cache (
    cache_key   TEXT        PRIMARY KEY,
    payload     JSONB       NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- TTL queries filter on age, so index fetched_at.
CREATE INDEX IF NOT EXISTS idx_provider_cache_fetched_at
    ON provider_cache (fetched_at);

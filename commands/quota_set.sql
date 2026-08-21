-- The ONLY writer of this channel's free-tier meter (whatsapp_inbox#37).
--
-- `free_tier_monthly_limit` is what the two ingest guards read to stop counting inbound messages
-- (`commands/message_ingest_msg.sql`, `commands/inbound_message_insert.sql`) and this module is
-- billed per message, so the column is the invoice, not a preference. It used to be written by
-- `settings.upsert` like any other field, which handed every holder of `manage_settings` — the
-- hub's `admin`, or the assistant acting for them — a one-command way to zero their own meter.
--
-- **The owner is billing, in the Cloud.** The SaaS already resolves this module's tier and its
-- `quota` and meters usage against it (`apps/whatsapp_inbox/services/billing.py` +
-- `apps/public/modules/usage.py`, ADR-0013/ADR-0032); the number here is a MIRROR of that fact.
-- ADR-0213 fixes the direction of travel — the SaaS declares, the hub acts, and there is no
-- SaaS→hub credential to push with — so the number arrives the way every other Cloud fact does:
-- the hub pulls it and calls this command. `internal: true` is what keeps that the only path: the
-- dispatcher answers `internal_command` to HTTP callers and API keys (hub#131/#145), so no screen,
-- no API key and no assistant can reach it.
--
-- **It seeds the singleton row.** Inbound ingestion does not wait for anybody to open the settings
-- screen, so the meter cannot either: a hub whose merchant never visited that page still has to
-- carry the allowance billing granted it. Every other column is left to its DDL default
-- (`migrations/postgres/001_init.sql`), which is exactly what `settings.get` already projects for
-- a hub with no row — creating it here changes no behaviour the merchant can see.
--
-- On conflict only the meter and the audit stamp move: this command has no opinion about the
-- fifteen fields the settings screen owns, and overwriting them with defaults would make a plan
-- change wipe the merchant's greeting.
--
-- `0` keeps meaning «no cap» (the guards only enforce above zero) — it is what a hub on an
-- unmetered plan gets, and what an unprovisioned hub has always had.
--
-- Runtime injects :new_id, :hub_id, :current_user_id, :now.
INSERT INTO whatsapp_inbox_settings
  (id, hub_id, free_tier_monthly_limit, is_deleted, created_by, updated_by, created_at, updated_at)
VALUES
  (:new_id, :hub_id, :monthly_limit, 0, :current_user_id, :current_user_id, :now, :now)
ON CONFLICT(hub_id) DO UPDATE SET
   free_tier_monthly_limit = excluded.free_tier_monthly_limit,
   updated_by              = :current_user_id,
   updated_at              = :now;

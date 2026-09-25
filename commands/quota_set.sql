-- The ONLY writer of this channel's meter — the allowance AND the spend (whatsapp_inbox#37, #155).
--
-- `free_tier_monthly_limit` is what the two ingest guards read to stop the channel
-- (`commands/message_ingest_msg.sql`, `commands/inbound_message_insert.sql`) and this module is
-- billed per message, so the column is the invoice, not a preference. It used to be written by
-- `settings.upsert` like any other field, which handed every holder of `manage_settings` — the
-- hub's `admin`, or the assistant acting for them — a one-command way to zero their own meter.
--
-- **The owner is billing, in the Cloud.** The SaaS already resolves this module's tier and its
-- `quota` and meters usage against it (`apps/whatsapp_inbox/services/billing.py` +
-- `apps/public/modules/usage.py`, ADR-0013/ADR-0032); the numbers here are a MIRROR of that fact.
-- ADR-0213 fixes the direction of travel — the SaaS declares, the hub acts, and there is no
-- SaaS→hub credential to push with — so they arrive the way every other Cloud fact does: the hub
-- pulls them and calls this command. `internal: true` is what keeps that the only path: the
-- dispatcher answers `internal_command` to HTTP callers and API keys (hub#131/#145), so no screen,
-- no API key and no assistant can reach it.
--
-- **The spend travels with the cap** (whatsapp_inbox#155). Until now only the cap came from the
-- platform and the spend was counted here, over this module's own inbound messages — a different
-- unit from the one that is sold, so the «Plan» tab and erplora.com showed the owner two numbers
-- for one allowance. `:monthly_usage` is the platform's own count of billable messages
-- (`usage.billable_messages`), and it is the number every reader uses from here on.
--
-- **`COALESCE(:monthly_usage, …)` is the half that decides whether this is safe.** The field is
-- OPTIONAL: the hub omits the key when the platform did not report a usable spend, and the
-- runtime binds what is not in the payload as SQL NULL. An absence means «I do not know», so it
-- keeps the stored figure — never resets it to zero — and, above all, the CAP still lands on that
-- same tick. A cap that stopped arriving because the spend was missing would be a metered channel
-- with no limit, which is worse than the defect this closes. A `0` that DOES arrive is a fact
-- about the month and is written.
--
-- **`monthly_usage_month` is why a figure may be trusted.** The payload carries the number but not
-- the month it counts, and this sync ticks once a day: without the stamp, a business that ended
-- September at 30/30 would spend up to 24 h of October with the channel shut on September's bill.
-- The month is the UTC `YYYY-MM` of `:now` — text domain, never `erp_month_start`
-- (whatsapp_inbox#24) — and it is written only WITH a figure, so an absent spend leaves the stamp
-- exactly as untouched as the figure it belongs to. Readers treat another month's figure as 0.
--
-- `CAST(:monthly_usage AS INTEGER) IS NULL` and not a bare `:monthly_usage IS NULL`: Postgres fixes
-- a parameter's type at its FIRST appearance and `IS NULL` contributes none, so an untyped bind
-- arriving NULL kills the PREPARE with 42P08 and the command stops running in EVERY hub — cap
-- included (`erplora validate`, rule `null-untyped`). INTEGER and not the TEXT the rule suggests by
-- default, because this bind is a count of messages and the COALESCE above already lands it in an
-- INTEGER column: deducing TEXT here and INTEGER there is `inconsistent types deduced for
-- parameter`, which is the same failure from the other side.
--
-- **It seeds the singleton row.** Inbound ingestion does not wait for anybody to open the settings
-- screen, so the meter cannot either: a hub whose merchant never visited that page still has to
-- carry the allowance billing granted it. Every other column is left to its DDL default
-- (`migrations/postgres/001_init.sql`) — creating the row here changes no behaviour the merchant
-- can see.
--
-- On conflict only the meter and the audit stamp move: this command has no opinion about any
-- other column of the row (today `approval_mode`, still read by the requests pipeline).
--
-- `0` keeps meaning «no cap» for the LIMIT (the guards only enforce above zero) — it is what a hub
-- on an unmetered plan gets, and what an unprovisioned hub has always had.
--
-- Runtime injects :new_id, :hub_id, :current_user_id, :now.
INSERT INTO whatsapp_inbox_settings
  (id, hub_id, free_tier_monthly_limit, monthly_usage, monthly_usage_month,
   is_deleted, created_by, updated_by, created_at, updated_at)
VALUES
  (:new_id, :hub_id, :monthly_limit,
   COALESCE(:monthly_usage, 0),
   CASE WHEN CAST(:monthly_usage AS INTEGER) IS NULL THEN '' ELSE substr(:now, 1, 7) END,
   0, :current_user_id, :current_user_id, :now, :now)
ON CONFLICT(hub_id) DO UPDATE SET
   free_tier_monthly_limit = excluded.free_tier_monthly_limit,
   monthly_usage           = COALESCE(:monthly_usage, whatsapp_inbox_settings.monthly_usage),
   monthly_usage_month     = CASE WHEN CAST(:monthly_usage AS INTEGER) IS NULL
                                  THEN whatsapp_inbox_settings.monthly_usage_month
                                  ELSE substr(:now, 1, 7) END,
   updated_by              = :current_user_id,
   updated_at              = :now;

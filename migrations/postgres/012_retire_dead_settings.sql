ALTER TABLE whatsapp_inbox_settings DROP COLUMN is_enabled;
ALTER TABLE whatsapp_inbox_settings DROP COLUMN account_mode;
ALTER TABLE whatsapp_inbox_settings DROP COLUMN auto_reply_enabled;
ALTER TABLE whatsapp_inbox_settings DROP COLUMN require_confirmation;
ALTER TABLE whatsapp_inbox_settings DROP COLUMN request_schema;
ALTER TABLE whatsapp_inbox_settings DROP COLUMN gpt_system_prompt;
ALTER TABLE whatsapp_inbox_settings DROP COLUMN input_modules;
ALTER TABLE whatsapp_inbox_settings DROP COLUMN output_modules;
ALTER TABLE whatsapp_inbox_settings DROP COLUMN auto_close_hours;
ALTER TABLE whatsapp_inbox_settings DROP COLUMN notify_staff_new_request;
ALTER TABLE whatsapp_inbox_settings DROP COLUMN greeting_message;
ALTER TABLE whatsapp_inbox_settings DROP COLUMN out_of_hours_message;

-- Whatsapp_inbox · migration 012 — the settings nobody reads are retired (whatsapp_inbox#127).
--
-- The prose is at the BOTTOM on purpose. This file is declared `kind: "contract"` in the manifest,
-- the only declaration under which the runtime accepts a `DROP`, and it accepts it by TRANSLATING
-- it: `migration_guard::set_aside_instead_of_dropping` turns `DROP COLUMN c` into
-- `RENAME COLUMN c TO _deprecated_c`. Metadata only, no row rewritten, the values stay. Reverting
-- is renaming back. A hub from before hub#1137 matched the verb at the start of the statement
-- text, so a header above the first `DROP` would have made it miss - nothing above the statements.
--
-- WHAT IS RETIRED, AND WHY IT IS SAFE. These twelve columns were the old Django settings form
-- ported as it was (001_init.sql). Since whatsapp_inbox#123 (ADR-0470) the Settings screen is three
-- steps and writes not one column of this module. Checked on origin of the 27 module repositories,
-- the hub and the SaaS - no query, command, WASM handler, recipe or runtime code reads any of them,
-- and the two doors that still named them (`settings.get`, `settings.upsert`) had no caller at all.
-- They leave in the same release, so the version that stops naming the columns is the `since`.
--
-- One statement per column - the rename accepts ONE column (hub#1145). And NO `IF EXISTS` - the
-- runtime carries it into the rename, and Postgres has no `RENAME COLUMN IF EXISTS` (a syntax
-- error that would stop the module from updating). A boot that dies halfway loses nothing - the
-- runtime sends the whole file as one batch, which Postgres runs as one implicit transaction.
-- Every column carried a DEFAULT, and a rename keeps it - so the one writer left (`_quota.set`,
-- which never named them) still inserts.
--
-- NOT retired here - `approval_mode`, still read by the requests pipeline
-- (`commands/_insert_request.sql`), which leaves with its own issue. And the billing meter
-- (`free_tier_monthly_limit`, `monthly_usage`, `monthly_usage_month`) stays, untouched.
--
-- WARNING No semicolons in this footer. The migration guard that runs on the fleet splits
-- statements by the semicolon without understanding comments (printing#23).

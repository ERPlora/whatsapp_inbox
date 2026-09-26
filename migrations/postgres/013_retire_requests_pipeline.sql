DROP TABLE whatsapp_inbox_request;
DROP TABLE whatsapp_inbox_request_counter;
ALTER TABLE whatsapp_inbox_settings DROP COLUMN approval_mode;

-- Whatsapp_inbox · migration 013 — the requests pipeline is retired (whatsapp_inbox#206).
--
-- The prose is at the BOTTOM on purpose, as in 012. This file is declared `kind: "contract"` in
-- the manifest, the only declaration under which the runtime accepts a `DROP`, and it accepts it
-- by TRANSLATING it: `migration_guard::set_aside_instead_of_dropping` turns `DROP TABLE t` into
-- `ALTER TABLE t RENAME TO _deprecated_t` and `DROP COLUMN c` into
-- `RENAME COLUMN c TO _deprecated_c`. Metadata only, no row rewritten, the values stay. Reverting
-- is renaming back.
--
-- WHAT IS RETIRED, AND WHY IT IS SAFE. The «Requests» tab left in whatsapp_inbox#193 because
-- nothing fed it - the recipes book straight into Appointments and Reservations, and a booking
-- waiting for review is confirmed in Appointments. This release takes out what the tab stood on -
-- the `requests.*` doors, their internal commands, permissions, events and the listener of
-- Appointments' answers. Checked on origin of the 27 module repositories, the hub and the SaaS -
-- after this release no query, command, WASM handler, recipe or runtime code reads the request
-- table, its per-day counter or `approval_mode` (whose only reader was `_insert_request`). They
-- leave in the same release, so the version that stops naming them is the `since`.
--
-- One statement per table or column - the rename accepts ONE name (hub#1145). NO `IF EXISTS` on
-- the column - the runtime carries it into the rename, and Postgres has no
-- `RENAME COLUMN IF EXISTS` (hub#2108). A boot that dies halfway loses nothing - the runtime sends
-- the whole file as one batch, which Postgres runs as one implicit transaction. The foreign key of
-- the request table to the conversations travels with the renamed table, so deleting a
-- conversation still cascades to its set-aside requests and blocks nothing. `approval_mode`
-- carried a DEFAULT, and a rename keeps it - so `_quota.set`, which never named it, still inserts.
--
-- WARNING No semicolons in this footer. The migration guard that runs on the fleet splits
-- statements by the semicolon without understanding comments (printing#23).

-- The last list of slots the automation offered this customer (whatsapp_inbox#76).
--
-- The «appointment from WhatsApp» recipe answers «do you have room tomorrow?» with a list she can
-- TAP. A tap comes back with the whole slot in its id, but a customer who WRITES «the 2nd» or
-- «12:30» starts a fresh run that never saw the list. What the automation sends leaves through the
-- kernel, not through this module, so it is not in `whatsapp_inbox_message` to be read back: the
-- recipe remembers it here (`whatsapp_inbox.conversations.remember_offer`) and the next run reads
-- it (`whatsapp_inbox.conversations.last_offer`).
--
-- `offered_slots` is the JSON array the assistant handed to `flow_answer`, stored as text exactly
-- as the recipe rendered it; `''` and `'[]'` both mean «nothing on offer». `offered_at` is when it
-- was offered (ISO-8601 text, ADR-0007 §1); NULL on every thread that was never offered anything.
-- Additive and nullable/defaulted, so every existing row stays valid without a backfill.
ALTER TABLE whatsapp_inbox_conversation
  ADD COLUMN IF NOT EXISTS offered_slots TEXT NOT NULL DEFAULT '';
ALTER TABLE whatsapp_inbox_conversation
  ADD COLUMN IF NOT EXISTS offered_at TEXT;

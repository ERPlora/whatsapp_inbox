-- Upserts the conversation THIS message belongs to. Keyed by (hub_id, wa_contact_id), the unique
-- index `uq_wa_conv_hub_contact` of migration 002 — one thread per customer, not one per message.
--
-- **The thread is the number at the OTHER end (`contact`), never the sender (`from`)**
-- (whatsapp_inbox#66). Since hub#1612 the poll asks the SaaS for `?direction=all`, so what arrives
-- is no longer only what customers sent: it also carries the ECHO of what the owner answered from
-- the WhatsApp Business app on their phone. In an echo `from` is the shop's own number, so keying
-- by it opened a conversation between the business and ITSELF and filed every reply there — the
-- customer's chat kept showing half a conversation. `contact` is the customer in both directions.
-- `COALESCE` because a hub older than hub#1612 sends no `contact` at all (the bind arrives as SQL
-- NULL): for every message such a hub could serve, the sender WAS the other end.
--
-- **`contact_phone` is normalised to E.164 here, and nowhere else.** Meta reports `from` as a
-- wa_id: digits with NO leading `+` (`34600111222`). The hub can only dial `+34600111222` —
-- `host_notify::check_recipient_syntax` refuses anything else, and the `notify` step of a flow
-- (hub#821) applies that same check to whatever a `recipient_query` grant reads. So this column is
-- the difference between a customer the hub can answer at 3 AM and one it cannot.
-- `ltrim(…, '+')` first so a number that already arrives in E.164 is not turned into `++34…`.
--
-- The id is minted by the database on purpose: the runtime injects ONE `:new_id` per command and
-- this command creates two rows, so `:new_id` goes to the message — the row that is always
-- created — and the conversation, which usually already exists, takes a fresh uuid that the
-- ON CONFLICT branch then throws away.
--
-- `contact_name` and `phone_number_id` are NOT updated on conflict: the core event carries neither,
-- and overwriting a name we know with an empty string we do not is how an inbox forgets its
-- customers. Runtime injects :hub_id, :current_user_id, :now.
INSERT INTO whatsapp_inbox_conversation
  (id, hub_id, wa_contact_id, contact_name, contact_phone, phone_number_id,
   status, unread_count, context, is_deleted, created_by, updated_by, created_at, updated_at)
VALUES
  (gen_random_uuid()::text, :hub_id,
   COALESCE(NULLIF((:contact)::text, ''), :from), '',
   '+' || ltrim(COALESCE(NULLIF((:contact)::text, ''), :from), '+'), '',
   'active', 0, '{}', 0, :current_user_id, :current_user_id, :now, :now)
ON CONFLICT (hub_id, wa_contact_id) DO UPDATE SET
  contact_phone = EXCLUDED.contact_phone,
  updated_at    = EXCLUDED.updated_at,
  updated_by    = EXCLUDED.updated_by;

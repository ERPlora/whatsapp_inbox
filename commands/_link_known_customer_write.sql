-- Links a WhatsApp conversation to the customer on file for its number — written by the
-- `link_known_customer` handler, the listener of this module's own `whatsapp_inbox.message.received`
-- (whatsapp_inbox#149). It is what makes the inbox know whose each thread is with NO automation
-- installed; the handler already decided WHICH customer (exact digits, exactly one card).
--
-- It only FILLS an empty link, never overwrites one: a person or a recipe that already said whose
-- the thread is knows more than a phone match does (two cards may have shared that number when the
-- link was made, or the owner fixed it by hand). `''` counts as empty — it is what a blank link
-- looked like before the public door refused blanks.
--
-- An already-linked thread therefore writes 0 rows, and that is correct: this command carries NO
-- `expect_rows` on purpose, or every message of a known customer would fail the listener.
--
-- `customer_id` stays a soft reference: this module never reads the customers table itself; the
-- handler got the card through the `customers.list` read the runtime pre-loaded.
-- Runtime injects :hub_id, :current_user_id, :now.
UPDATE whatsapp_inbox_conversation
SET customer_id = :customer_id,
    updated_by  = :current_user_id,
    updated_at  = :now
WHERE hub_id = :hub_id AND wa_contact_id = :wa_contact_id AND is_deleted = 0
  AND (customer_id IS NULL OR customer_id = '');

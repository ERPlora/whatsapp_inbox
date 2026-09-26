-- Remembers WHOSE this WhatsApp conversation is, so the inbox filter by customer stops answering
-- nothing.
--
-- Keyed by the CONTACT, not by the conversation id, and that is deliberate: what the automations
-- hold is the phone the message came from (`input.from`), never the thread's id — keying by the id
-- would make each recipe read `whatsapp_inbox.conversations.list` first, and therefore carry a
-- plain `query` grant for it instead of the `recipient_query` narrowed to `#contact_phone` they
-- carry today. `uq_wa_conv_hub_contact (hub_id, wa_contact_id)` is UNIQUE, so the contact picks out
-- exactly one thread of this business anyway.
--
-- `customer_id` is a soft reference (this module never touches the customers table); the caller
-- resolved her against the hub. The schema refuses a blank one: a recipe whose customer step found
-- nobody renders '' and would ERASE a good link instead of writing one.
--
-- Runtime injects :hub_id, :current_user_id, :now.
UPDATE whatsapp_inbox_conversation
SET customer_id = :customer_id,
    updated_by  = :current_user_id,
    updated_at  = :now
WHERE hub_id = :hub_id AND wa_contact_id = :wa_contact_id AND is_deleted = 0;

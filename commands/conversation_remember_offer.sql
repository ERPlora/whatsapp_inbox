-- Remembers the list of slots the automation just offered this customer (whatsapp_inbox#76), so
-- that her next message — «the 2nd», «12:30» — can be resolved against it.
--
-- Keyed by the CONTACT like `conversation_link_customer.sql`, for the same reason: what the recipe
-- holds is the phone the message came from (`input.from`), and `uq_wa_conv_hub_contact` makes the
-- contact pick out exactly one thread of this business. The recipe calls it on EVERY turn, also
-- when it offered nothing (`[]`): that is what clears a list once she has booked, cancelled or
-- moved, so a stray «the 2nd» days later finds nothing to book.
--
-- Runtime injects :hub_id, :current_user_id, :now.
UPDATE whatsapp_inbox_conversation
SET offered_slots = :offered_slots,
    offered_at    = :now,
    updated_by    = :current_user_id,
    updated_at    = :now
WHERE hub_id = :hub_id AND wa_contact_id = :wa_contact_id AND is_deleted = 0;

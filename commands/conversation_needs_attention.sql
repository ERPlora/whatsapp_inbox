-- Marks the conversation as «needs attention» (whatsapp_inbox#238): the automation could not answer
-- this customer and told her someone from the team would. The inbox puts the thread on top with a
-- visible label until somebody of the business answers her (`inbound_conversation_stats.sql` clears
-- it on the live echo of the owner's reply).
--
-- Keyed by the CONTACT like `conversation_remember_offer.sql`: what the recipe holds is the phone
-- the message came from (`input.from`), and `uq_wa_conv_hub_contact` makes the contact pick out
-- exactly one thread of this business.
--
-- `COALESCE` keeps the FIRST time she was left waiting: if the automation gives up on her again
-- before anyone answered, «waiting since» must not move forward and hide how long she has waited.
--
-- Runtime injects :hub_id, :current_user_id, :now.
UPDATE whatsapp_inbox_conversation
SET needs_attention_at = COALESCE(needs_attention_at, :now),
    updated_by         = :current_user_id,
    updated_at         = :now
WHERE hub_id = :hub_id AND wa_contact_id = :wa_contact_id AND is_deleted = 0;

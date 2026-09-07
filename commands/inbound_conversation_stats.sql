-- Moves the conversation to the top of the inbox and marks it unread — but ONLY if the message
-- before it is the one THIS execution wrote.
--
-- The `EXISTS` is the whole point, and since whatsapp_inbox#30 it asks about `:new_id` and not
-- about `:wa_message_id`. `:new_id` is a fresh uuid the runtime mints per command execution, so the
-- row exists only if OUR insert landed — which is the honest test for both ways it may not have:
--
--   * free tier exhausted → the statement before this one inserted 0 rows, and an `unread_count`
--     that counts a message nobody can open is a badge that never clears
--   * duplicate → the insert was absorbed by `ON CONFLICT DO NOTHING`, because the public command
--     `whatsapp_inbox.messages.ingest` had already ingested this `wa_message_id`, or the relay
--     redelivered after a crash. Asking for the `wa_message_id` would find the FIRST delivery's row
--     and bump the badge for a message the thread already showed — the old question could not tell
--     «mine landed» from «somebody else's is already there».
--
-- **Whose thread, and whether anybody still has to read it** (whatsapp_inbox#66). The thread is the
-- number at the OTHER end (`contact`), not the sender: since hub#1612 this door also sees the ECHO
-- of what the owner answered from the WhatsApp Business app, and there `from` is the shop itself.
-- Same `COALESCE` fallback as its two sibling statements — a hub older than hub#1612 sends no
-- `contact`, and for everything such a hub could serve the sender WAS the other end.
--
-- The badge only counts what somebody in the business still has to read, which is neither of two
-- things this door now delivers:
--
--   * the owner's OWN reply (`direction = 'outbound'`) — they wrote it, so marking the thread
--     unread because of it is a badge that accuses the merchant of not reading themselves;
--   * the 180-day coexistence backlog (`source = 'history'`) — messages already read on the phone
--     months ago; counting them would greet a merchant who has just connected their number with
--     hundreds of unread conversations and no way to clear them.
--
-- An unknown `direction` DOES count: unread means «nobody here has read this», and the one case
-- where that is certainly false is the business having written it. `last_message_at` moves for
-- every message, backlog included — ordering the historical thread by when it was really said needs
-- a timestamp the event does not carry today (whatsapp_inbox#92).
--
-- The lookup goes through the primary key. Runtime injects :new_id, :hub_id, :current_user_id, :now.
UPDATE whatsapp_inbox_conversation
SET last_message_at = :now,
    unread_count    = unread_count + CASE
      WHEN COALESCE(NULLIF((:direction)::text, ''), 'inbound') = 'outbound' THEN 0
      WHEN COALESCE(NULLIF((:source)::text, ''), 'live') <> 'live' THEN 0
      ELSE 1
    END,
    updated_at      = :now,
    updated_by      = :current_user_id
WHERE hub_id = :hub_id
  AND wa_contact_id = COALESCE(NULLIF((:contact)::text, ''), :from)
  AND is_deleted = 0
  AND EXISTS (
    SELECT 1 FROM whatsapp_inbox_message m
    WHERE m.hub_id = :hub_id AND m.id = :new_id
  );

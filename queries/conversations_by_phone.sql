-- The conversation of ONE number, matched exactly — the recipient lookup of the «Confirmed!»
-- recipe (whatsapp_inbox#279).
--
-- `conversations.list` filters `contact_phone` as «contains» because the inbox search needs it
-- (WHATSAPP_INBOX-F05), and a recipient lookup cannot live with that: an appointment holding
-- `600111` matched `+34600111222`, somebody else's chat. Here the phone has to be E.164 (`+`, a
-- country code that does not start with 0, 7 to 15 digits, nothing else) and equal to the
-- thread's `contact_phone`, which the inbox stores in E.164 since F03.
--
-- ALWAYS one row, so the recipe can stop on each reason with its own condition:
--   phone_is_international  false for anything that is not E.164 (empty, spaces, no `+`, NULL)
--   has_thread              a live conversation of this hub has exactly that number
--   conversation_id, contact_phone   that conversation's, or NULL
-- Runtime injects :hub_id.
SELECT asked.phone_is_international,
       (thread.id IS NOT NULL) AS has_thread,
       thread.id AS conversation_id,
       thread.contact_phone
FROM (
  SELECT COALESCE(CAST(:phone AS TEXT) ~ '^\+[1-9][0-9]{6,14}$', false) AS phone_is_international
) AS asked
LEFT JOIN LATERAL (
  SELECT id, contact_phone
  FROM whatsapp_inbox_conversation
  WHERE hub_id = :hub_id
    AND is_deleted = 0
    AND asked.phone_is_international
    AND contact_phone = CAST(:phone AS TEXT)
  ORDER BY last_message_at DESC NULLS LAST, id
  LIMIT 1
) AS thread ON true;

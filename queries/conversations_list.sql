-- The hub's conversations (optional filters by status and contact search).
-- Ported from ConversationService.list_conversations. Runtime injects :hub_id.
--
-- `attention_first` is the inbox's default order (whatsapp_inbox#238): the conversations the
-- automation could not answer (`needs_attention_at` set) go first, then the rest, each group with
-- the most recent activity first. It is one sortable text key because the list engine sorts by ONE
-- column: '1|<last_message_at>' ranks above '0|<last_message_at>' in `desc`, and within a group the
-- UTC timestamps compare as text in time order.
--
-- A phone is searched as a NUMBER, not as text (whatsapp_inbox#291). The thread keeps the number
-- the way WhatsApp gives it (E.164, `+34600111222`), and the list engine compares text, so
-- «600 111 222» found nobody. When the question is made only of phone characters (digits, spaces,
-- `+`, dashes, dots, slashes, parentheses), its digits are compared with the phone's digits, with
-- its leading zeros dropped first: that is the `00` international prefix and a national trunk `0`
-- («0034 600 111 222», «07700 900123»), while a part of the number still finds it, like the search
-- of WhatsApp Web. A question with a letter in it («Marta 2») stays a name search.
--   · `phone_match` serves the search box: the engine ORs `contains` over the `search` columns, so
--     the column repeats the question when the number matches, and is empty otherwise.
--   · `:f_contact_phone` serves the Phone column filter, applied here and not by the engine (the
--     manifest does not declare it as an engine filter, or the engine would AND a text `contains`).
-- Both binds are the engine's optional ones and appear only inside COALESCE (absent = no filter).
-- A query cannot call the handler (`erplora_guest_sdk::phone`): the full libphonenumber reading
-- answers «is this the same number», and a search box also has to answer «is this a part of it».
SELECT id, customer_id, assigned_to_id, phone_number_id, wa_contact_id,
       contact_name, contact_phone, status, last_message_at, unread_count, needs_attention_at,
       CASE WHEN needs_attention_at IS NULL THEN '0|' ELSE '1|' END
         || COALESCE(last_message_at, '') AS attention_first,
       CASE
         WHEN COALESCE(:search, '') ~ '^[0-9 +()./-]+$'
          AND ltrim(regexp_replace(COALESCE(:search, ''), '[^0-9]', '', 'g'), '0') <> ''
          AND regexp_replace(COALESCE(contact_phone, ''), '[^0-9]', '', 'g')
              LIKE '%' || ltrim(regexp_replace(COALESCE(:search, ''), '[^0-9]', '', 'g'), '0') || '%'
         THEN COALESCE(:search, '')
         ELSE ''
       END AS phone_match
FROM whatsapp_inbox_conversation
WHERE hub_id = :hub_id AND is_deleted = 0
  AND (
    COALESCE(:f_contact_phone, '') = ''
    OR (COALESCE(:f_contact_phone, '') ~ '^[0-9 +()./-]+$'
        AND ltrim(regexp_replace(COALESCE(:f_contact_phone, ''), '[^0-9]', '', 'g'), '0') <> ''
        AND regexp_replace(COALESCE(contact_phone, ''), '[^0-9]', '', 'g')
            LIKE '%' || ltrim(regexp_replace(COALESCE(:f_contact_phone, ''), '[^0-9]', '', 'g'), '0') || '%')
    OR (NOT (COALESCE(:f_contact_phone, '') ~ '^[0-9 +()./-]+$'
             AND ltrim(regexp_replace(COALESCE(:f_contact_phone, ''), '[^0-9]', '', 'g'), '0') <> '')
        AND lower(COALESCE(contact_phone, '')) LIKE '%' || lower(COALESCE(:f_contact_phone, '')) || '%')
  )

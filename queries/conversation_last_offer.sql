-- The list of slots this customer was offered in the last 24 hours, if any (whatsapp_inbox#76).
--
-- No row means nothing is on offer: never offered, offered more than a day ago, or cleared with
-- an empty list after she booked, cancelled or moved. A `query` step with result=first reads that
-- as `found: false`, which is how the assistant knows a bare «the 2nd» has nothing to point at.
-- 24 hours is a day's conversation: long enough to answer after lunch, short enough that tomorrow's
-- «the 2nd» does not book from a list whose slots may be long gone (the assistant still checks the
-- slot is free before booking it).
--
-- Runtime injects :hub_id and :now.
SELECT offered_slots, offered_at
FROM whatsapp_inbox_conversation
WHERE hub_id = :hub_id
  AND wa_contact_id = :wa_contact_id
  AND is_deleted = 0
  AND offered_slots NOT IN ('', '[]')
  AND offered_at IS NOT NULL
  AND erp_dt(offered_at) >= erp_dateadd(:now, -24, 'hours');

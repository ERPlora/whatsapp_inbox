-- The conversations of this hub the link sweep has not asked about yet (whatsapp_inbox#163):
-- alive, with no customer (NULL or `''`, the same «unlinked» as the link writes), never swept.
-- Oldest first, so a hub with a long history empties its backlog in the order it was built.
-- Bounded: the sweep's handler gets the rows in memory and one sweep is one transaction — the
-- rest waits for the next run. Runtime injects :hub_id.
SELECT id, wa_contact_id
FROM whatsapp_inbox_conversation
WHERE hub_id = :hub_id AND is_deleted = 0
  AND (customer_id IS NULL OR customer_id = '')
  AND link_swept_at IS NULL
ORDER BY created_at, id
LIMIT 200

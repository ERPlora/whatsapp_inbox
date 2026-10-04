-- WhatsApp inbox · «Erase this number's data», step 0/2 — erase what the RETIRED «Requests» tray
-- extracted from this thread (whatsapp_inbox#264).
--
-- The manual twin of `_on_customer_anonymized_requests.sql`: the SAME SET list (compared by
-- `tests/number_erasure.pg.test.py`), only the WHERE differs — every request hanging from the
-- thread the admin opened, whatever sheet the tray linked it to. The table is the one migration 013
-- set aside (`_deprecated_whatsapp_inbox_request`); writing it needs a hub with hub#2461.
--
-- The `hub_id` guards are load-bearing: the outer one keeps another hub's request that points at
-- this thread id out of reach, the inner one keeps another hub's thread id from naming anything
-- here. A request already blank and soft-deleted is skipped: pressing twice stamps nothing more
-- and keeps the first `deleted_at`. This statement carries no `expect_rows` — a thread the tray
-- never saw is the ordinary case; the refusal stays anchored on the thread statement.
-- Runtime injects :hub_id, :current_user_id, :now.
UPDATE _deprecated_whatsapp_inbox_request
   SET data           = '{}',
       raw_summary    = '',
       notes          = '',
       failure_reason = '',
       is_deleted     = 1,
       deleted_at     = COALESCE(deleted_at, :now),
       updated_by     = :current_user_id,
       updated_at     = :now
 WHERE hub_id = :hub_id
   AND (data <> '{}' OR raw_summary <> '' OR notes <> '' OR failure_reason <> '' OR is_deleted = 0)
   AND conversation_id IN (
         SELECT c.id
           FROM whatsapp_inbox_conversation c
          WHERE c.hub_id = :hub_id
            AND c.id = :conversation_id
       );

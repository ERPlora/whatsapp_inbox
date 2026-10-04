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
   AND CAST(:customer_id AS TEXT) <> ''
   AND (data <> '{}' OR raw_summary <> '' OR notes <> '' OR failure_reason <> '' OR is_deleted = 0)
   AND (customer_id = :customer_id
        OR conversation_id IN (
             SELECT c.id
               FROM whatsapp_inbox_conversation c
              WHERE c.hub_id = :hub_id
                AND c.customer_id = :customer_id
           ));

-- WhatsApp inbox · `customer.anonymized`, step 0/2 — erase what the RETIRED «Requests» tray kept
-- of the customer (whatsapp_inbox#264).
--
-- The tray left in whatsapp_inbox#206: migration 013 retired its table, and the runtime SETS ASIDE a
-- retired table instead of dropping it (`_deprecated_whatsapp_inbox_request`, every hub's rows
-- still in it). What the tray extracted from her messages is still there — the parsed `data` (name,
-- number, what she asked for), the `raw_summary`, the staff's `notes` and the `failure_reason`
-- sentence, which quotes her. Those four columns are blanked and the request soft-deleted; the row
-- stays, so nothing pointing at its id dangles. `failure_code` (a namespaced code), the reference
-- number and the opaque ids are not personal data on their own and stay.
--
-- Hers = carrying her customer id, OR hanging from one of her threads (the tray often saved a
-- request before anyone linked the thread to a sheet). Same event and payload as steps 1 and 2.
--
-- Writing a set-aside table needs a hub with hub#2461: the install gate accepts UPDATE/DELETE on the
-- module's OWN `_deprecated_<id>*` tables and nothing else there. The gate does NOT add the tenant
-- filter — the `hub_id` guards here do, both of them load-bearing: the table holds every hub's
-- rows, and `customer_id` is an opaque id that may name another person in another hub. The
-- empty-id guard keeps a degenerate event from erasing every blank-linked request.
--
-- IDEMPOTENT: the outbox is at-least-once; a request already blank and soft-deleted is skipped, so
-- a redelivery stamps nothing and keeps the first `deleted_at`. No `expect_rows`: a customer the
-- tray never saw is the ordinary case. The SET list is the same text as
-- `conversation_erase_requests.sql`, compared by `tests/number_erasure.pg.test.py`.

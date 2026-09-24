-- Links the unlinked conversations of a NUMBER to the customer whose card was just saved — written
-- by the `link_customer_threads` handler, the listener of `customer.created` / `customer.updated`
-- (whatsapp_inbox#160). The handler already decided WHICH customer (the one card carrying that
-- number) and hands over the number as the card knows it, in digits without leading zeros.
--
-- The thread is found by NUMBER, not by its exact key (whatsapp_inbox#162): WhatsApp keys it with
-- the international number (`34600111222`) while the owner very often types the card without the
-- country code (`600 111 222`). Same rule as `customers.by_phone` and the handler: equal, or the
-- thread's number is the card's plus a 1-3 digit country code. A longer number that merely
-- CONTAINS it is somebody else, and the handler never sends fewer than 7 digits.
--
-- It only FILLS an empty link (NULL or `''`), never overwrites one, and carries NO `expect_rows`:
-- an already-linked thread writes 0 rows on purpose. Runtime injects :hub_id, :current_user_id, :now.
UPDATE whatsapp_inbox_conversation
SET customer_id = :customer_id,
    updated_by  = :current_user_id,
    updated_at  = :now
WHERE hub_id = :hub_id AND is_deleted = 0
  AND (customer_id IS NULL OR customer_id = '')
  AND (
    ltrim(regexp_replace(wa_contact_id, '[^0-9]', '', 'g'), '0') = CAST(:phone AS TEXT)
    OR (
      length(ltrim(regexp_replace(wa_contact_id, '[^0-9]', '', 'g'), '0'))
        - length(CAST(:phone AS TEXT)) BETWEEN 1 AND 3
      AND right(ltrim(regexp_replace(wa_contact_id, '[^0-9]', '', 'g'), '0'),
                length(CAST(:phone AS TEXT))) = CAST(:phone AS TEXT)
    )
  );

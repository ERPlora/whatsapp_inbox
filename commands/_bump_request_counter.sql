-- Atomically bumps the day's request counter (upsert, ADR-0008).
-- First intent of `parse_inbound_message`; `_insert_request` reads the counter back
-- by subquery in the SAME transaction. The runtime injects :new_id and :hub_id; :day
-- comes from the handler (YYYYMMDD derived from context.now).
--
-- The self-reference MUST stay table-qualified: inside `ON CONFLICT ... DO UPDATE SET`
-- an unqualified column name is ambiguous in PostgreSQL between the target table and
-- the `excluded` pseudo-table (`column reference "last_number" is ambiguous` — the
-- statement does not even parse). It is the PERSISTED value that must grow:
-- `excluded.last_number` is always the literal 1 from VALUES, which would freeze every
-- reference number of the day at WA-YYYYMMDD-0001.
INSERT INTO whatsapp_inbox_request_counter (id, hub_id, day, last_number)
VALUES (:new_id, :hub_id, :day, 1)
ON CONFLICT (hub_id, day)
DO UPDATE SET last_number = whatsapp_inbox_request_counter.last_number + 1;

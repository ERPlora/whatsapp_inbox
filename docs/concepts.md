# WhatsApp Inbox — Concepts

The things people get wrong on their first day.

## Fulfilling a request creates nothing anywhere else

This is the module's whole reason to exist and it is the thing that does not work.

A request is meant to become a real object — a reservation, an order, a quote — in the module that
owns it. The handler has that branch, and the runtime **forbids a module's handler from writing into
another module**. So the branch returns `cross_module_dispatch_unsupported` and the only thing that
happens is the request's status moving to `fulfilled`.

**Read a fulfilled request as "a human dealt with this elsewhere."** The link fields, which would say
which object was created and where, stay empty.

## Replying does not happen here, and that is on purpose

This module cannot send a WhatsApp message: no command sends anything, and the manifest declares no
`capabilities`, so the runtime could not reach Meta even if one existed. The credentials live in the
SaaS proxy — architecture §9.3 is explicit that the hub never stores Meta's.

What answers a customer is a flow's **notify** step (hub#821): it goes out through the outbox, with
retries, backoff and dead-letter, and it addresses the contact through a `recipient_query` grant
over `whatsapp_inbox.conversations.list#contact_phone`. That is why the ingest normalises the phone
to E.164 — a number without its `+` is a customer the hub cannot answer.

The `send_message` permission was **retired in whatsapp_inbox#29**. It named nothing, and a
permission that gates nothing is not a restriction: it is a label on an empty box that answers *yes*
to an audit of "can this employee reply?".

## Messages arrive on their own; requests do not

Since [#27](https://github.com/ERPlora/whatsapp_inbox/pull/27) the hub polls the SaaS for inbound
messages and raises the core event `hub.whatsapp.message_received`; this module listens to it and
runs its own internal ingest command. So an inbound message lands in a conversation by itself.

The public ingest command is still there for the channel pipeline. Both doors require the
connections permission precisely because they are a channel intake point, not a user action, and
neither declares a webhook receiver or network access to Meta.

What does **not** happen on its own is turning a message into a structured request — that is the
flow template shipped in `flows/`.

## One `wa_message_id` is one message, whichever door it comes through

Two commands write the same message row: the public `messages.ingest` and the internal
`_ingest_inbound_message` that the core event runs. Since **whatsapp_inbox#30** a partial unique
index over `(hub_id, wa_message_id)` sits underneath both, and both absorb the conflict silently —
so the same message delivered twice leaves **one row and one unread bump**, and neither caller
gets an error for having tried.

That mattered to the bill until whatsapp_inbox#155: the free tier was measured by counting inbound
messages of the month, so a duplicate row was the merchant's quota being spent twice on one message.
The allowance is now the platform's own count of **billable** messages — the ones the business
sends, which is what is sold and what Meta charges for — so a duplicate no longer touches the bill.
It is still a second copy of the customer's message in the thread the merchant reads.

Soft-deleting a message releases its `wa_message_id` again — the index is partial over
`is_deleted = 0` — so deleting is not a one-way door.

**What is still per-call, not per-message:** the `whatsapp_inbox.message.received` **event**. A
declarative command emits on every execution, so a second ingest of the same message emits a second
event even though it wrote no row. Nothing listens to it today, and the exactly-once guarantee for
reactions lives one level up, on the core event `hub.whatsapp.message_received`
(`id = "wa-<wa_message_id>"` in the outbox), which is what the shipped flow triggers on. The missing
primitive is tracked in [hub#1076](https://github.com/ERPlora/hub/issues/1076).

## The request schema is supplied, not enforced by the module

When a request is ingested, its parsed data is validated against the hub's **dynamic request
schema** — but the schema is **passed in by the caller**, which read it from settings first. The
module checks a subset: which fields are required and what type they should be.

That means validation is only as good as the schema the caller passed. It is deliberately
**non-authoritative**.

## Approval mode decides where a request starts

- **`manual`** — a new request is `pending_review` and waits for somebody.
- **`auto`** — it starts `confirmed`, ready to be fulfilled.

It is a per-hub setting, not a per-request choice.

## Fulfil only from confirmed, and never delete a fulfilled request

The status guard lives in the SQL: fulfilment only applies to a `confirmed` request, and deletion
refuses anything already `fulfilled`.

A guard that does not hold is a **silent no-op** — nothing changes and nothing explains why. Re-read
the request after acting.

## Confidence is clamped and unknown types become `custom`

Two normalisations happen on ingest and surprise people:

- the confidence score is forced into the range 0 to 1;
- a `request_type` that is not one of the known ones becomes **`custom`**, rather than being
  rejected.

So a request with an odd type is not lost; it is filed as custom.

## The customer is a soft reference

The customer on a conversation or a request is an id, resolved through `customers`' **public
queries**. This module never reads that module's tables, and there is no foreign key. The same is
true of who a conversation is assigned to.

## Templates are stored, not synchronised

A template carries its status at Meta, and **nothing checks with Meta**. If Meta approves or rejects
a template, this hub will not know until somebody updates it by hand.

Creating a template here does not submit it to Meta either.

## The permissions are unusually admin-heavy

Worth internalising because it explains a lot of "I cannot see that":

- **Templates and settings are admin-only** — a *manager* cannot even list templates.
- **Assigning a conversation is admin-only**, because it is governed by the settings permission.
- **Ingesting messages and requests is admin-only** (connections).
- A **manager** can approve, reject and fulfil requests.
- An **employee** can only read conversations and requests.

## Numbering is per day and atomic

`WA-YYYYMMDD-NNNN`, unique per hub, from a counter bumped in the same transaction as the insert. This
was deliberately solved inside the module rather than waiting for a runtime feature.

## Everything deletes softly

Conversations, messages, requests and templates are marked deleted, never erased. Deleting a
conversation takes its messages and requests with it.

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

## There is no way to send a message

The module defines a `send_message` permission and grants it to everybody, including employees.
**There is no command behind it.** No outbound message can be created, no reply can be sent, and the
auto-reply settings describe behaviour that nothing performs.

An inbox you can read and not answer is what this module currently is.

## Nothing brings messages in on its own

There is an ingest command, and it works — it upserts the conversation from the contact, stores the
message and emits an event. But:

- no webhook receiver is declared;
- no network access to Meta's API is declared in the manifest.

So messages arrive only if something outside calls that command. It requires the connections
permission precisely because it is a channel intake point, not a user action.

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

# WhatsApp Inbox — Overview

## What this module does

WhatsApp Inbox is the shared inbox for a WhatsApp Business channel. It keeps a **conversation** per
contact with its **messages**, extracts structured **requests** from those conversations — an order, a
reservation, an appointment, a quote — and holds the **message templates** approved by Meta plus the
channel configuration.

A request goes through review: it is created, approved or rejected, and finally fulfilled.

## What this module does NOT do — read this first

This module is a **data model and a workflow**, and several pieces you would expect are not wired:

- **It cannot send a WhatsApp message.** There is a `send_message` permission and there is **no
  command that sends anything**. No outbound message exists.
- **It does not receive messages by itself.** There is an ingest command, but nothing declares a
  webhook or the network access to Meta's API — the manifest declares no network allowlist.
- **Fulfilling a request cannot create anything in another module.** This is the module's central
  purpose and it **does not work** — see below.
- **It does not call an LLM.** The parsed data is expected to arrive already parsed.
- **It does not sync templates with Meta.**
- **It does not route conversations per employee.** The table exists; no command or screen does.

## The central limitation: fulfilment does not dispatch

The point of a request is to become something real — a reservation in `reservations`, an order in
`sales`. The fulfilment handler has a branch for exactly that, and **it cannot run**: the runtime
forbids a module's handler from writing into another module, so that branch returns
`cross_module_dispatch_unsupported`.

What **does** work is the simple branch: marking a request `fulfilled`. Nothing is created anywhere
else, and the link fields stay empty.

Practically: **a fulfilled request is a note that somebody handled it by hand.**

## Modules it connects to

**Depends on `customers`**, referenced softly — the customer id on a conversation or a request is a
loose reference resolved through public queries, never by reading another module's tables.

**Events it emits**

| Event | When |
|---|---|
| `whatsapp_inbox.message.received` | an inbound message is ingested |
| `whatsapp_inbox.request.created` | a request is extracted from a message |
| `whatsapp_inbox.request.approved` / `.rejected` / `.fulfilled` / `.deleted` | the request moves |
| `whatsapp_inbox.conversation.assigned` | a conversation is assigned |
| `whatsapp_inbox.template.created` / `.updated` / `.deleted` | templates change |
| `whatsapp_inbox.settings.updated` | the configuration is saved |

**Events it listens to** — one, since [#27](https://github.com/ERPlora/whatsapp_inbox/pull/27):
`hub.whatsapp.message_received`, the core event the hub raises when it polls an inbound WhatsApp
message from the SaaS. It runs `whatsapp_inbox._ingest_inbound_message`, an **internal** command of
this same module — a listener may only ever call a command of its own module.

That closes the intake gap described above **for messages**: an inbound message now lands in a
conversation by itself, exactly once. It does **not** close the request gap — nothing still turns a
message into a structured request on its own; that is the flow template shipped in `flows/`.

## The vocabulary

| Concept | Values |
|---|---|
| **Request type** | `order`, `reservation`, `appointment`, `quote`, `transport`, `custom` |
| **Request status** | `pending_review`, `confirmed`, `rejected`, `fulfilled`, `cancelled` |
| **Message direction** | `inbound`, `outbound` |
| **Account mode** | `shared` or `per_employee` |
| **Approval mode** | `auto` or `manual` — decides whether a new request starts confirmed |
| **Template category** | `MARKETING`, `UTILITY`, `AUTHENTICATION` |
| **Template status at Meta** | `pending`, `approved`, `rejected` |

## Request numbering

Requests carry a stable reference `WA-YYYYMMDD-NNNN`, unique per hub, from an atomic per-day counter
read in the same transaction that writes the request.

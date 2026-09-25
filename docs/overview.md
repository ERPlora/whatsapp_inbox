# WhatsApp Inbox — Overview

## What this module does

WhatsApp Inbox is the shared inbox for a WhatsApp Business channel. It keeps a **conversation** per
contact with its **messages**, links each conversation to the customer on file for its number, and
holds the **message templates** approved by Meta plus the channel configuration.

It keeps **no list of requests**. What a customer asks for on WhatsApp is booked by an automation
(the flow templates in `flows/`) straight into Appointments or Reservations; a booking the business
wants to review first waits there, pending confirmation, and is confirmed from Appointments. The old
«Requests» list and everything behind it were retired in whatsapp_inbox#193 and whatsapp_inbox#206.

## What this module does NOT do — read this first

This module is a **data model and a workflow**, and several pieces you would expect are not wired:

- **It cannot send a WhatsApp message.** No command sends anything and the manifest declares no
  `capabilities`, so the runtime could not reach Meta either. Replying is a flow's **notify** step
  (hub#821), which goes by the outbox and the SaaS proxy — where the credentials live. The
  `send_message` permission was retired in whatsapp_inbox#29 because it gated nothing.
- **It does not talk to Meta at all.** No webhook receiver and no network allowlist are declared
  here. Inbound messages reach the module through the hub's own poll and the core event
  `hub.whatsapp.message_received`, not through this manifest.
- **It does not call an LLM.** Understanding the message is the job of the flow's `ai` step.
- **It does not sync templates with Meta.**
- **It does not route conversations per employee.** The table exists; no command or screen does.

## Modules it connects to

**Depends on `customers`**, referenced softly — the customer id on a conversation is a
loose reference resolved through public queries, never by reading another module's tables.

**Events it emits**

| Event | When |
|---|---|
| `whatsapp_inbox.message.received` | an inbound message is ingested |
| `whatsapp_inbox.conversation.assigned` | a conversation is assigned |
| `whatsapp_inbox.template.created` / `.updated` / `.deleted` | templates change |

**Events it listens to** — one, since [#27](https://github.com/ERPlora/whatsapp_inbox/pull/27):
`hub.whatsapp.message_received`, the core event the hub raises when it polls an inbound WhatsApp
message from the SaaS. It runs `whatsapp_inbox._ingest_inbound_message`, an **internal** command of
this same module — a listener may only ever call a command of its own module.

That closes the intake gap described above: an inbound message lands in a conversation by itself,
exactly once. Turning it into a booking is the flow template shipped in `flows/`.

## The vocabulary

| Concept | Values |
|---|---|
| **Message direction** | `inbound`, `outbound` |
| **Account mode** | `shared` or `per_employee` |
| **Template category** | `MARKETING`, `UTILITY`, `AUTHENTICATION` |
| **Template status at Meta** | `pending`, `approved`, `rejected` |

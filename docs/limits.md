# WhatsApp Inbox — Limits and troubleshooting

## What does not work — read before relying on this module

| Capability | State |
|---|---|
| **Fulfilling a request creates the object in another module** | ❌ **Broken.** Returns `cross_module_dispatch_unsupported`; only the status changes |
| **Sending a WhatsApp message** | ❌ **Does not exist.** The permission exists; no command does |
| **Receiving messages automatically** | ❌ No webhook and no declared network access to Meta |
| **Auto-replies, greetings, out-of-hours messages** | ❌ Configurable, never sent |
| **Calling an LLM to parse a message** | ❌ Not here — the parsed data must arrive already parsed |
| **Syncing template status with Meta** | ❌ Stored, never checked |
| **Per-employee routing** | ❌ Table exists; no command, no screen |
| **Fulfilling a request** (status only) | ✅ Works |
| **Ingesting a message and a request** | ✅ Works, when something calls it |
| **Approve / reject / delete a request** | ✅ Works |
| **Templates and settings CRUD** | ✅ Works |

## Errors and refusals

| Error | What happened | What to do |
|---|---|---|
| `cross_module_dispatch_unsupported` | Fulfilment tried to create an object in another module | Do it by hand in the destination module |
| Request schema validation failed | The parsed data is missing a required field or has a wrong type | Fix the payload, or the schema in settings |

These fail as **silent no-ops**:

| Situation | Result |
|---|---|
| Fulfilling a request that is not `confirmed` | Nothing changes |
| Deleting a request that is already `fulfilled` | Nothing changes |
| Approving or rejecting from a state that does not allow it | Nothing changes |

## Accepted values

| Field | Values |
|---|---|
| Request type | `order`, `reservation`, `appointment`, `quote`, `transport`, `custom` — **unknown becomes `custom`** |
| Request status | `pending_review`, `confirmed`, `rejected`, `fulfilled`, `cancelled` |
| Message direction | `inbound`, `outbound` |
| Account mode | `shared`, `per_employee` |
| Approval mode | `auto`, `manual` |
| Template category | `MARKETING`, `UTILITY`, `AUTHENTICATION` |
| Template status at Meta | `pending`, `approved`, `rejected` |
| Confidence score | clamped to 0–1 |
| Free-tier monthly limit | 0 means no limit |

## Caps and sizes

| Limit | Value |
|---|---|
| Rows per page (conversations, messages, requests, templates) | 50 |
| Maximum rows a paginated request may ask for | 500 |
| Requests per day per hub, by numbering | 9999 |
| Conversations per contact | 1 — the ingest upserts by contact |
| Live messages per `wa_message_id` and hub | 1 — unique index, both ingestion doors absorb the repeat (whatsapp_inbox#30) |

## Permissions per action

| To do this | You need |
|---|---|
| See conversations and messages | `whatsapp_inbox.view_conversation` |
| See requests | `whatsapp_inbox.view_request` |
| Approve, reject or fulfil a request | `whatsapp_inbox.change_request` |
| Delete a request | `whatsapp_inbox.delete_request` |
| Assign a conversation; list, create, update or delete templates; read or save the settings | `whatsapp_inbox.manage_settings` |
| Ingest a message or a request | `whatsapp_inbox.manage_connections` |

By role:

- **admin** — everything.
- **manager** — view conversations and requests (thread included), and approve / reject / mark as
  handled. **Cannot** assign a conversation, cannot see templates, cannot see or change the
  settings, cannot ingest, cannot delete.
- **employee** — read conversations, their threads and requests. Nothing else.

## Dependencies

**`customers` is required** and installed with the module, but referenced softly — through its public
queries, with no foreign key.

**Nothing depends on this module**, and it listens to no events.

The `output_modules` setting names the modules a request would be dispatched to, but **that
dispatch does not run**, so those modules are not really dependencies — nothing is called.

## When something looks wrong

**"I fulfilled a request and no reservation appeared."** Expected. Cross-module dispatch is blocked.
Create it by hand in `reservations`.

**"I cannot reply to a customer."** Not from this screen, and there is no `send_message` permission
any more (whatsapp_inbox#29 retired it — it gated nothing). The hub answers WhatsApp through a
flow's **notify** step, which is where the channel credentials are.

**"No messages are arriving."** The hub polls the SaaS and raises `hub.whatsapp.message_received`,
which this module listens to — check that the channel is connected on the SaaS side. What is NOT
declared here is a webhook receiver or network access to Meta.

**"The same message appears twice."** It cannot since whatsapp_inbox#30: a partial unique index over
`(hub_id, wa_message_id)` sits under both ingestion doors. On a hub that carried duplicates from
before, migration 005 kept the oldest copy of each and soft-deleted the rest.

**"The auto-reply never went out."** This module sends nothing, auto-replies included — that is a
flow's notify step, and the auto-reply settings here have no owner (WASM-TODO.md §5).

**"I cannot find the channel settings screen."** There is none yet
([whatsapp_inbox#6](https://github.com/ERPlora/whatsapp_inbox/issues/6)).

**"A manager cannot see the templates."** Correct — templates are behind the settings permission,
which is admin-only.

**"A manager cannot assign a conversation."** Also correct, and for the same reason.

**"Fulfilling did nothing."** The request was not `confirmed`. The guard is a silent no-op.

**"I cannot delete this request."** It is already `fulfilled`. That is deliberate.

**"A request came in with a weird type."** Unknown types are normalised to `custom` rather than
rejected.

**"The confidence score is not what the parser said."** It is clamped to the range 0 to 1.

**"A request was accepted with missing data."** Validation is done against the schema **the caller
passed in**, and it checks a subset. It is deliberately non-authoritative — tighten the schema in
settings.

**"Meta approved my template and the hub still says pending."** Nothing synchronises with Meta.
Update it by hand.

**"New requests skip review."** The approval mode is `auto`. Set it to `manual`.

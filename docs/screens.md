# WhatsApp Inbox — Screens

The module contributes three tabs to the hub navigation: **Inbox**, **Requests** and **Templates**.

## Inbox — conversations

Every WhatsApp conversation of the hub (`whatsapp_inbox.conversations.list`, 50 rows per page).
Requires `whatsapp_inbox.view_conversation` — an employee can read this.

A conversation carries the contact, a soft reference to the customer, who it is assigned to, its
status, the time of the last message, the unread count, and the bot's context.

### Open a conversation and read the thread

The **Open** action of a row loads the conversation (`whatsapp_inbox.conversations.get`) and its
messages (`whatsapp_inbox.messages.list`, oldest first) into a panel above the list. Requires
`whatsapp_inbox.view_conversation`, the same as the list — an employee can read a thread.

Messages that carry no text (a photo, a location, a button reply) show the **kind** Meta reported
instead of an empty bubble.

Until whatsapp_inbox#29 those two reads had no caller and a module called *inbox* could not open a
message. That matters since appointments#38: approving a request creates a real appointment, so
whoever approves has to be able to read what the customer actually wrote.

### Assign a conversation

From the open thread. Empty employee id = **unassign**, which is the SQL's own contract. Requires
`whatsapp_inbox.manage_settings` — **admin only**, which means a manager cannot assign conversations.

### Reply to a customer

**Not from this screen.** The module declares no send command and no `capabilities`, so the runtime
could not reach Meta even if it did. The hub answers WhatsApp through a flow's **notify** step
(hub#821), which goes by the outbox and the SaaS proxy — the only place the channel credentials
live. The `send_message` permission was retired in whatsapp_inbox#29: it gated nothing, and a
permission that gates nothing answers *yes* to an audit that should say no.

### How a message gets in

An ingest command upserts the conversation from the contact, stores the message and emits
`whatsapp_inbox.message.received`. It requires `whatsapp_inbox.manage_connections` — **admin only** —
because it is the channel's intake point, not a user action.

Since [#27](https://github.com/ERPlora/whatsapp_inbox/pull/27) the hub's own poll of the SaaS raises
the core event `hub.whatsapp.message_received` and this module listens to it, so an inbound message
lands in a conversation by itself. **Exactly once**: since whatsapp_inbox#30 a partial unique index
over `(hub_id, wa_message_id)` sits under both ingestion doors, so the same message arriving twice
leaves one row, one unit on the free-tier meter and one unread bump.

There is still no webhook receiver and no network access to Meta declared here.

## Requests

The structured requests extracted from conversations (`whatsapp_inbox.requests.list`, 50 rows per
page). Requires `whatsapp_inbox.view_request`.

Each request carries its reference `WA-YYYYMMDD-NNNN`, its **type**, its **status**, the structured
data, a plain-language summary, a confidence score, and the link fields for the object it would have
created.

### How a request is created

The ingest command takes an already-parsed payload and:

1. validates it against the hub's **dynamic request schema** — the required fields and the field
   types configured in settings;
2. clamps the confidence score to a value between 0 and 1;
3. normalises the type, turning anything unknown into `custom`;
4. allocates the reference and writes the request, with its starting status decided by the hub's
   **approval mode** — `auto` starts it confirmed, `manual` leaves it for review.

Requires `whatsapp_inbox.manage_connections` — **admin only**.

### Approve or reject a request

Both are guarded by the request's current status and both emit their event. Requires
`whatsapp_inbox.change_request` — a manager has it, an employee does not.

### Mark a request as handled

The **Mark as handled** row action moves the request to `fulfilled`, and only from `confirmed` — on
any other status the button is visible but disabled, because the guard lives in the SQL and a
command that matches 0 rows explains nothing to whoever pressed it.

> ⚠️ **Nothing is created in another module,** and that is by design, not a gap waiting to be
> filled: cross-module dispatch from a handler is forbidden (hub#659, ADR-0283 §7) precisely because
> it would be a capability with no owner. The link fields stay empty, and a fulfilled request means
> *somebody dealt with this by hand*. To materialise a request, use a flow with an explicit grant —
> auditable and revocable — or, for an appointment, the booking panel above.

Requires `whatsapp_inbox.change_request`.

### Delete a request

The **Delete** row action asks for confirmation in the page, then soft-deletes it. **A request that
is already fulfilled cannot be deleted** (the audit chain to the linked object has to survive), so
the action is disabled on those rows. Requires `whatsapp_inbox.delete_request` — **admin only**.

## Templates

The WhatsApp Business templates approved by Meta (`whatsapp_inbox.templates.list`, 50 rows per page).
Requires `whatsapp_inbox.manage_settings` — **admin only**, so a manager cannot even list them.

A template has a **category** (`MARKETING`, `UTILITY`, `AUTHENTICATION`), a language, a header, a
body, a footer, its Meta template id, its **status at Meta** (`pending`, `approved`, `rejected`), its
variables, and an active flag.

Create, update and delete are all admin-only. Create and **edit** share the panel behind the «+» of
the table's toolbar — the **Edit** row action loads the template into it, and the fields the panel
does not show (header, footer, variables, active flag) travel back unchanged, so editing a body
never blanks a header somebody set. **Delete** asks for confirmation in the page.

> Editing a template resets its Meta status to `pending`: Meta re-approves content.

> The Meta status is stored, not synchronised. Nothing checks with Meta whether a template was
> approved.

## Settings — the channel

> ⚠️ **There is no settings screen.** `whatsapp_inbox.settings.get` and
> `whatsapp_inbox.settings.upsert` exist and nothing in the UI calls them — the channel is
> configured by whoever installs the module. Tracked in
> [whatsapp_inbox#6](https://github.com/ERPlora/whatsapp_inbox/issues/6), and listed with its reason
> in the `PENDING` block of `tests/surface_has_a_door.contract.test.py`. What follows is what the
> settings mean, not a screen you can open.

Read with `whatsapp_inbox.settings.get` and saved with `whatsapp_inbox.settings.upsert`. Requires
`whatsapp_inbox.manage_settings` — **admin only**.

| Setting | What it controls |
|---|---|
| **Account mode** | `shared` or `per_employee` |
| **Approval mode** | `auto` (requests start confirmed) or `manual` (they wait for review) |
| Auto-reply enabled, greeting, out-of-hours message | Automatic replies — **nothing sends them** |
| Require confirmation | Whether a request needs confirming |
| **Request schema** | The dynamic schema an ingested request is validated against |
| System prompt | The prompt for the assistant that parses messages |
| **Input modules** | Which modules' public queries provide catalogue context |
| **Output modules** | Which modules a request type would be dispatched to |
| Auto-close hours | When an idle conversation closes |
| Free-tier monthly limit | 0 means no limit |

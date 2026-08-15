# WhatsApp Inbox — Screens

The module contributes three tabs to the hub navigation: **Inbox**, **Requests** and **Templates**.

## Inbox — conversations

Every WhatsApp conversation of the hub (`whatsapp_inbox.conversations.list`, 50 rows per page).
Requires `whatsapp_inbox.view_conversation` — an employee can read this.

Open a conversation for its detail (`whatsapp_inbox.conversations.get`) and its messages
(`whatsapp_inbox.messages.list`).

A conversation carries the contact, a soft reference to the customer, who it is assigned to, its
status, the time of the last message, the unread count, and the bot's context.

### Assign a conversation

Assigns it to an agent or a team. Requires `whatsapp_inbox.manage_settings` — **admin only**, which
means a manager cannot assign conversations.

### Reply to a customer

**You cannot.** There is no command that sends a message. The `send_message` permission exists and
grants access to nothing. See [limits.md](limits.md).

### How a message gets in

An ingest command upserts the conversation from the contact, stores the message and emits
`whatsapp_inbox.message.received`. It requires `whatsapp_inbox.manage_connections` — **admin only** —
because it is the channel's intake point, not a user action.

**Nothing calls it automatically**: no webhook receiver and no network access to Meta are declared.

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

### Fulfil a request

Marks the request `fulfilled`, and only from `confirmed`.

> ⚠️ **Nothing is created in another module.** The dispatch branch that would create the reservation,
> the order or the quote **cannot run** and returns `cross_module_dispatch_unsupported`. The link
> fields stay empty. Do the real work by hand in the destination module.

Requires `whatsapp_inbox.change_request`.

### Delete a request

Soft-deletes it. **A request that is already fulfilled cannot be deleted.** Requires
`whatsapp_inbox.delete_request` — **admin only**.

## Templates

The WhatsApp Business templates approved by Meta (`whatsapp_inbox.templates.list`, 50 rows per page).
Requires `whatsapp_inbox.manage_settings` — **admin only**, so a manager cannot even list them.

A template has a **category** (`MARKETING`, `UTILITY`, `AUTHENTICATION`), a language, a header, a
body, a footer, its Meta template id, its **status at Meta** (`pending`, `approved`, `rejected`), its
variables, and an active flag.

Create, update and delete are all admin-only.

> The Meta status is stored, not synchronised. Nothing checks with Meta whether a template was
> approved.

## Settings — the channel

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

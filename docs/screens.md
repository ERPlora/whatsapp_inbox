# WhatsApp Inbox — Screens

The module contributes three tabs to the hub navigation: **Inbox**, **Requests** and **Templates**.

## Inbox — conversations

Every WhatsApp conversation of the hub (`whatsapp_inbox.conversations.list`, 50 rows per page).
Requires `whatsapp_inbox.view_conversation` — an employee can read this.

A conversation carries the contact, a soft reference to the customer, who it is assigned to, its
status, the time of the last message, the unread count, and the bot's context.

The list shows the **most recent activity first** (`last_message_at`, newest on top), like any
inbox. When the number is connected, WhatsApp also delivers the conversations of the last months;
each of those messages keeps the time it was **actually sent** (Meta's own timestamp), so an old
conversation stays down the list where it belongs and its thread reads in the order things were
said. A history message that arrives without a usable time is dated when it reached the hub.

Times are shown on the **business clock** (the hub's time zone, not the device's) and in the hub's
language: the «Last message» column reads the time if it is from today, «Yesterday», or the date if
older; each message in the thread reads the same way, with its time next to «Yesterday» or the date.

### Open a conversation and read the thread

The **Open** action of a row loads the conversation (`whatsapp_inbox.conversations.get`) and its
messages (`whatsapp_inbox.messages.list`, oldest first) into a panel above the list. Requires
`whatsapp_inbox.view_conversation`, the same as the list — an employee can read a thread.

Messages that carry no text (a location, a button reply) show the **kind** Meta reported instead of
an empty bubble.

**Attachments** (#192). A photo or a sticker the customer sent shows inside the thread as soon as it
opens, with its caption. A voice note or a video gets a **Play** button, and a document a
**Download** button with its file name: they are fetched only when tapped, because every attachment
travels from WhatsApp through the platform. While it loads the bubble says so; if it fails it says
so and offers **Try again**. The file is kept only while the thread is open.

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
leaves one row and one unread bump.

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
body, a footer, its Meta template id, its **status at Meta** (`not_sent`, `pending`, `approved`, `rejected`, `paused`, `disabled`, `deleted`), its
variables, and an active flag.

Create, update and delete are all admin-only. Create and **edit** share the panel behind the «+» of
the table's toolbar — the **Edit** row action loads the template into it, and the fields the panel
does not show (header, footer, variables, active flag) travel back unchanged, so editing a body
never blanks a header somebody set. **Delete** asks for confirmation in the page.

> Editing a template resets its Meta status to `pending`: Meta re-approves content.

> Meta's verdicts are refreshed once, when the tab opens — never on a timer. Meta names a template
> by **name + language**. A template this hub sent to Meta that Meta no longer lists (deleted in
> WhatsApp Manager) is marked `deleted` and kept, so the owner's text is not lost; only a fresh
> answer that lists at least one template can mark it. Templates Meta holds and this hub does not
> (created in WhatsApp Manager) are imported with their header, body, footer, example values and
> Meta's verdict (#179), once per name + language, and never over one the owner deleted here (the
> command refuses with `template_already_here` and the tab takes it as the normal answer: no notice,
> no phantom `template.created`). Since #180 an image/video/document header (its KIND —
> `header_format`; the file is chosen when a message is sent) and quick reply, link and call buttons
> (`buttons`, Meta's order) come in too: the panel lists them and keeps the template read-only, with
> no «Guardar», because saving would register it at Meta without them. Those with parts this module
> has no field for (a carousel, a limited-time offer, a copy-code or Flow button, a location header,
> a header variable, named `{{name}}` variables) are not imported without them: they are named in a
> notice above the table, `name (language)`.

## Settings — the channel

`<erp-whatsapp-inbox-settings>` — three blocks in this order: **the channel**, **what you use this
WhatsApp for**, and **the requests**. Read with `whatsapp_inbox.settings.get` and saved with
`whatsapp_inbox.settings.upsert`. Requires `whatsapp_inbox.manage_settings` — **admin only**.

**The channel** shows the meter (the billable messages this hub has spent this month against the
plan's allowance — both read-only, both counted by the platform and written by their only writer,
`whatsapp_inbox._quota.set`, fed by the Cloud) and embeds the shell's
`<erp-whatsapp-connect>`, which is where the number is connected by scanning Meta's QR with the
WhatsApp Business app. There is no credential to type: Meta's token lives Fernet-sealed in the SaaS
and the hub never sees it.

### What do you use WhatsApp for?

A shortcut into Automations, and deliberately nothing more: it does not create the flow or switch it
on. Each card names a use this hub can actually run — the module of the recipe has to be installed —
says what it does, and opens the gallery with that template named — or, once the automation is
already set up, the list of automations, where the owner's flow is. Without the `flows` module there
is no destination at all, so the block points at the app list instead.

Each card also says whether that automation is **already set up here**
([#79](https://github.com/ERPlora/whatsapp_inbox/issues/79)), so the salon that has been taking
appointments through WhatsApp for weeks is not invited to build a second one that answers the same
message. The answer comes from `flows.automations.status` — read-only, three integers about the one
event and the one command that identify the use, never `manage_flows`:

| What the card shows | When |
|---|---|
| **Active** + «View it» → the automations list | at least one automation listens to the use's event, may run its command and is switched on |
| **Paused** + «View it» → the automations list | it is set up, and switched off |
| **Unfinished** + «View it» → the automations list | something listens to the event but was never granted any command — where the gallery leaves a half-finished setup, since it creates every template paused and ungranted |
| no badge + «Set it up» → the template card | there is none — **or** the question could not be answered (an older `flows`, a denied permission). The card never says more than it knows |

«View it» never names the template card: the gallery scrolls that card into view and its one button
is «Use», which would build the second automation the badge exists to prevent. The status answer
carries no id on purpose, so the list is the closest the card can bring the owner to their flow.

### The requests

The one decision this screen offers: **approval mode** — whether a request the assistant parsed
lands confirmed or waits for a person to review it (read by `commands/_insert_request.sql`).

Everything the old bot used to configure — greeting, auto-reply, out-of-hours text, the prompt,
which modules feed it — is said by the FLOW that answers now (`WASM-TODO.md`, revision of
2026-08-11, pm#112 / ADR-0283). Those columns still exist and `settings.upsert` still requires them,
so the screen carries them back untouched; it does not OFFER them, because a switch that promises
behaviour no code reads is a dead switch.

#### The columns, and what each one means

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

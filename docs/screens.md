# WhatsApp Inbox — Screens

The module contributes two tabs to the hub navigation: **Inbox** and **Templates**.

## Inbox — conversations

Every WhatsApp conversation of the hub (`whatsapp_inbox.conversations.list`, 50 rows per page).
Requires `whatsapp_inbox.view_conversation` — an employee can read this.

A conversation carries the contact, a soft reference to the customer, who it is assigned to, its
status, the time of the last message, the unread count, and the bot's context.

The list shows **who is waiting first**, then the **most recent activity first**
(`last_message_at`, newest on top), like any inbox. A conversation the automation could not answer
— its assistant failed or answered with nothing, and the customer was told that someone from the
team would write — is marked **«Needs attention»** next to the contact and goes to the top of the
list. The opened conversation shows the same mark and a note explaining how it goes away: answer the
customer from the WhatsApp Business app on the phone, and the mark is removed as soon as that reply
reaches the hub. Her own next message does not remove it, and neither do the old messages of the
history. When the number is connected, WhatsApp also delivers the conversations of the last months;
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
opens, with its caption. Tapping a photo opens it large, in a full-screen viewer that pages through
every photo of the thread (arrows or the keys ← →) and closes with ✕ or Esc. A voice note or a video gets a **Play** button, and a document a
**Download** button with its file name: they are fetched only when tapped, because every attachment
travels from WhatsApp through the platform. While it loads the bubble says so; if it fails it says
so and offers **Try again**. The file is kept only while the thread is open.
WhatsApp sends voice notes as OGG/Opus, which Safari on iPhone, iPad and older Macs cannot play
(#223): on a device that cannot play it the button says **Download** instead of **Play**, and the
bubble says the device cannot play it and hands over the file (with its `.ogg`, `.mp3`… extension)
to open with another app. A player that fails on the downloaded file falls back the same way.

Until whatsapp_inbox#29 those two reads had no caller and a module called *inbox* could not open a
message. Whoever confirms a booking asked for over WhatsApp has to be able to read what the customer
actually wrote.

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

## Requests — retired

There is no «Requests» tab any more (whatsapp_inbox#193). Nothing fed it: the WhatsApp recipes book
straight into Appointments or Reservations, so the owner saw a list that was always empty. A booking
that waits for the owner's OK is a **pending appointment**, and it is confirmed in Appointments, next
to the rest of the diary. The requests commands, queries, table and events behind it were retired
too (whatsapp_inbox#206).

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
> (`buttons`, Meta's order) come in too. Since #185 the panel **edits buttons**: add up to ten —
> quick reply, link (a fixed `https://` address) or call (a number with its country code), at most two
> links and one call — each with a label of up to 25 characters; quick replies are kept together
> because Meta refuses them interleaved with links and calls, and «Guardar» stays off while a button
> lacks its label, link or number. They are stored in `buttons` and registered at Meta with the rest,
> so a template brought with plain buttons is edited here too. A media header (#218) or a link with a
> variable (`…/{{1}}`) still keeps the template read-only, listing its parts, with no «Guardar»,
> because saving would register it at Meta without them. Those with parts this module
> has no field for (a carousel, a limited-time offer, a copy-code or Flow button, a location header,
> more than one header variable) are not imported without them: they are named in a notice above the
> table, `name (language)`. Since #230 a text header with ONE variable (`{{1}}` or `{{name}}`, never
> mixed with the other kind in the body) comes in with its example (`header_example`, Meta's or a
> stand-in), and «Save» sends that example back to the registry. A template with named `{{name}}` body variables is imported and edited like any
> other (#186, #196): «Guardar» sends one example per distinct name, in first-appearance order.
>
> **Variable samples (#208).** Under the body the panel shows one «Sample for {{n}}» field per
> variable, as WhatsApp Manager does: numbered `{{1}}…{{n}}` in number order, named ones in
> first-appearance order. Meta reviews the template with them and refuses it without, so «Guardar»
> stays off while a numbered variable has no sample; a named one starts with its own name. Opening a
> template fills each field with its stored sample; removing a variable from the body drops its
> sample. The samples are stored in `variables` and sent to Meta with the rest.

## Settings — the channel

`<erp-whatsapp-inbox-settings>` — three steps (whatsapp_inbox#123): **connect the number**, **say
what you use this WhatsApp for**, and **one switch** per use. Requires
`whatsapp_inbox.manage_settings` — **admin only**. The screen writes no setting of this module: the
one decision it offers («bookings confirm themselves / I review them first») belongs to the module
that owns the diary (`appointments.settings.set_auto_confirm_online`,
`reservations.settings.set_auto_confirm`).

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

When the hub does not offer a card because an app its automation needs is missing, paused or too
old, the card is replaced by a warning that names **that** app and what to do — «“Book
appointments” needs the Staff app, and it is paused. Turn it back on in Apps.» — with a button to
Apps ([#210](https://github.com/ERPlora/whatsapp_inbox/issues/210)). «Book appointments» needs
Appointments, Customers, Services and Staff; «Book a table» needs Reservations and Customers. On a
hub that does not say which app fails yet, the warning stays the general «Update Appointments or
Reservations».

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

### When the module improves a reply you already turned on

Turning an automatic reply on builds it once, from the recipe the module shipped that day, and
updating the app never rewrites it on its own: the reply may carry changes made by hand in
Automations, and nothing is overwritten without being asked
([#241](https://github.com/ERPlora/whatsapp_inbox/issues/241)). When the module has since shipped an
improved recipe for a card — its own reply or the confirmation that goes with it — the card says
«There is an improved version of this automatic reply» with an **Update** button. The first tap only
asks, naming the consequence: the new version replaces the reply, including any hand-made changes,
and it stays on or off exactly as it is. Confirming hands over only the recipes the hub reported as
outdated; a card whose reply is up to date, or whose hub cannot tell, shows nothing. It is the same
restore that the Automations gallery offers as «Restore the factory version».

### What this screen does not store

The old bot's settings — greeting, auto-reply, out-of-hours text, «require confirmation», the prompt,
which modules feed it, auto-close hours, staff notification, the on/off switch, the account mode and
the request schema — were retired in whatsapp_inbox#127: nothing read them, and a switch that
promises behaviour no code reads is a dead switch. What an automatic reply says is written in the
FLOW that answers (Automations), which the owner edits without republishing the module. The values
a hub had saved are set aside in the database (`_deprecated_*` columns), not destroyed.

The only numbers the channel still keeps are the billing meter — the monthly allowance and what was
spent — written by billing alone (`whatsapp_inbox._quota.set`) and read with
`whatsapp_inbox.usage.get`.

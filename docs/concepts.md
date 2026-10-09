# WhatsApp Inbox — Concepts

The things people get wrong on their first day.

## Requests were retired: the diary owns a booking

Until whatsapp_inbox#206 the module kept its own «requests» — a structured object parsed from a
conversation (appointment, reservation, order, quote), with an approval mode, a status machine and a
fulfil step meant to create the real object in another module. None of it worked end to end: nothing
ingested a request, and fulfilling one could not write into another module. The table, its counter,
the `approval_mode` setting, the `requests.*` queries and commands and the `request.*` events were
removed (migration 013).

A booking asked for over WhatsApp is now made by the recipes in `flows/` directly in `appointments`
or `reservations`, and a booking waiting for a person is confirmed there, in the diary.

## Replying does not happen here, and that is on purpose

This module cannot send a WhatsApp message: no command sends anything, and the manifest declares no
`capabilities`, so the runtime could not reach Meta even if one existed. The credentials live in the
SaaS proxy — architecture §9.3 is explicit that the hub never stores Meta's.

What answers a customer is a flow's **notify** step (hub#821): it goes out through the outbox, with
retries, backoff and dead-letter, and it addresses the contact through a `recipient_query` grant
over `whatsapp_inbox.conversations.list#contact_phone`. That is why the ingest normalises the phone
to E.164 — a number without its `+` is a customer the hub cannot answer.

**When the automation cannot answer, the inbox remembers it** (whatsapp_inbox#238). If the
assistant of a WhatsApp recipe fails or answers with nothing, the recipe apologises to the customer
(«someone from the team will answer you here soon») and then calls
`whatsapp_inbox.conversations.needs_attention` for her contact. The conversation keeps
`needs_attention_at` — when the automation FIRST gave up on her; a second failure does not move it —
and the inbox lists it first with a «Needs attention» mark. The mark is cleared by the live echo of
a reply the business sends from the WhatsApp Business app (the only outbound message that reaches
the hub; what the automation itself sends never comes back as an echo), and by nothing else.

**And the business hears about it on every screen** (whatsapp_inbox#244). The module declares a
counter on the hub's notification bell, `whatsapp_inbox.needs_attention`, fed by the query
`whatsapp_inbox.conversations.count_needs_attention`: the number of conversations of this hub with
`needs_attention_at` set. The bell (in the top bar, whatever screen the owner is on) shows
«WhatsApp customers waiting for an answer» with that number while it is above zero, and tapping it
opens the inbox, where those conversations are listed first. It is derived state, not a message: it
goes away by itself exactly when the inbox mark does, and only people who can open the inbox
(`view_conversation`) see it.

The `send_message` permission was **retired in whatsapp_inbox#29**. It named nothing, and a
permission that gates nothing is not a restriction: it is a label on an empty box that answers *yes*
to an audit of "can this employee reply?".

## Messages arrive on their own

Since [#27](https://github.com/ERPlora/whatsapp_inbox/pull/27) the hub polls the SaaS for inbound
messages and raises the core event `hub.whatsapp.message_received`; this module listens to it and
runs its own internal ingest command. So an inbound message lands in a conversation by itself.

The public ingest command is still there for the channel pipeline. Both doors require the
connections permission precisely because they are a channel intake point, not a user action, and
neither declares a webhook receiver or network access to Meta.

What reacts to a message — answering, booking — is the flow templates shipped in `flows/`.

## The monthly allowance limits what is sent, never what comes in

What the plan sells is the WhatsApp messages the business **sends**. So every message a customer
writes is stored, also once this month's allowance is spent (whatsapp_inbox#287; before it, a live
message at the cap vanished from the inbox with nothing saying why). At the cap the two booking
replies read `whatsapp_inbox.usage.cap_reached` in their first step and stand down before the
acknowledgement and the assistant — no turn of the assistant spent, nothing booked — and mark the
conversation «Needs attention», so it rises to the hub's bell and someone answers from the phone.
The inbox shows a warning while the cap lasts. If the meter cannot be read, the reply carries on as
if there were no cap. The figures are the platform's and the hub copies them once a day, so the
pause can start and end up to a day late.

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

## The customer is a soft reference

The customer on a conversation is an id, resolved through `customers`' **public
queries**. This module never reads that module's tables, and there is no foreign key. The same is
true of who a conversation is assigned to.

## A message from a number on file tells the inbox whose the conversation is

No automation is needed. Every time a message arrives, the inbox looks for a customer whose phone
is **the same number** as the one that wrote (a longer number that merely contains it is somebody else) and
links the conversation to her. The number is compared as a number, not as text: the card may say
`+34600111222`, `+34 600-111-222`, `0034 600 111 222` or just `600 111 222` without the country
code, and it is still her (whatsapp_inbox#162). Numbers shorter than 7 digits never identify
anybody. The «from WhatsApp» automations still look the card up the old way (#165).
From then on, filtering the inbox by that customer finds the thread.

It only fills an **empty** link. If a person or an automation already said whose the conversation
is, the phone match never changes it. It links nobody when two different customers share the number
(a family phone): a person decides that one.

It also works the other way round (whatsapp_inbox#160). When somebody wrote **before** she was on
file — the bookings automation does not create a card — or her card had a wrong number, saving her
card (creating it, or correcting its phone) links her conversation right away, with the same rules:
exact number, only an empty link, nobody when two cards share it.

And a conversation from **before** any of this existed — her card untouched, and she has not written
since — is linked on its own too (whatsapp_inbox#163). A few minutes after the module is updated, a
background sweep asks the same question once for every conversation that still has no customer:
same rules, only an empty link, nobody when two cards share the number. It works in batches, so a
hub with a long history may take a little while to get through all of them. A conversation it could
not link (nobody on file with that number) is not asked again; it gets linked the moment she writes
or a card with her number is saved.

## Templates are stored, not synchronised

A template carries its status at Meta, and **nothing checks with Meta**. If Meta approves or rejects
a template, this hub will not know until somebody updates it by hand.

Creating a template here does not submit it to Meta either.

## The permissions are unusually admin-heavy

Worth internalising because it explains a lot of "I cannot see that":

- **Templates and settings are admin-only** — a *manager* cannot even list templates.
- **Assigning a conversation is admin-only**, because it is governed by the settings permission.
- **Ingesting messages is admin-only** (connections).
- A **manager** and an **employee** can only read conversations and their threads.

## Everything deletes softly — except an erased customer

Conversations, messages and templates are marked deleted, never erased. Deleting a conversation
takes its messages with it.

The one exception is the right to erasure (GDPR art. 17). When a customer's data is erased from her
sheet in Customers («Erase data»), her WhatsApp threads and their messages are emptied of every
personal datum — number, name, text, media link, raw WhatsApp payload, bot context — and marked
deleted. Only threads **linked to that sheet** are erased: a conversation that was never linked to
her is not touched. A plain «Delete» of the sheet keeps the conversations.

For somebody the sheet cannot reach — a person who wrote once and never had a customer sheet, or
whose thread was never linked to hers — an admin opens the conversation and presses **«Erase this
number's data»** (whatsapp_inbox#263). After a confirmation that names the number, that thread and
every message in it are emptied of exactly the same data as the erasure from the sheet, closed and
marked deleted. There is one thread per number in a hub, so the thread is the number. If the person
writes again, a new thread opens that is not linked to anyone. If the same person also has a
customer sheet, erase it there too: this button does not touch Customers.

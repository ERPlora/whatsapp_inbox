# WhatsApp Inbox — Limits and troubleshooting

## What does not work — read before relying on this module

| Capability | State |
|---|---|
| **Sending a WhatsApp message** | ❌ **Does not exist.** The permission exists; no command does |
| **Receiving messages automatically** | ❌ No webhook and no declared network access to Meta |
| **Auto-replies, greetings, out-of-hours messages** | ❌ Not here — what an automatic reply says is written in the flow that answers (Automations); the old settings that never sent anything were retired (#127) |
| **Requests (parsed bookings waiting for approval)** | ❌ Retired (#206) — a booking asked for over WhatsApp is made by the recipes in `flows/` directly in Appointments or Reservations, and one waiting for a person is confirmed there |
| **Syncing template status with Meta** | ✅ Each time the Templates tab opens (never on a timer). A template deleted in WhatsApp Manager is marked «Deleted in WhatsApp Manager», not removed; one created there is imported with its text and verdict (#179) — image/video/document headers and quick reply, link and call buttons included (#180, editable here since #185), and named body variables (`{{name}}`, #186, editable here since #196; a media header or a link button with a variable keeps the panel read-only) — unless it uses a carousel, a limited-time offer, a copy-code or Flow button, a location header or a header variable — those are named in a notice |
| **Per-employee routing** | ❌ Table exists; no command, no screen |
| **Ingesting a message** | ✅ Works |
| **Templates CRUD** | ✅ Works |
| **Knowing whose a conversation is** | ✅ Automatic when the number is on a customer card, typed any way (`+34 600 111 222`, `0034…`, or `600 111 222` without the country code, #162; 7 digits at least). A card without a prefix is a number of the business's country (the hub's country setting): the same digits from another country's prefix are somebody else and are not linked to her (#167). Where the leading 0 is part of the international number (Italian landlines: `06 1234567` is `+39 06 1234567`; likewise San Marino, the Vatican, Côte d'Ivoire, Congo, Burkina Faso, Gabon, Niger and Tajikistan, the countries libphonenumber has without a trunk prefix), the card keeps it (#201); saving the card links her conversation, while linking her when she writes also needs the Customers lookup to keep that 0 (customers#82); only fills an empty link. A customer filed (or whose phone is corrected) after she wrote gets her conversation when the card is saved (#160); a conversation from before is linked by a background sweep a few minutes after the update, in batches of 200 every 15 minutes (#163) |

## Accepted values

| Field | Values |
|---|---|
| Message direction | `inbound`, `outbound` |
| Template category | `MARKETING`, `UTILITY`, `AUTHENTICATION` |
| Template button | `QUICK_REPLY` (label only), `URL` (label + a fixed `http(s)://` address, no variable), `PHONE_NUMBER` (label + number with country code, `+34…`); none on an `AUTHENTICATION` template |
| Template status at Meta | `not_sent`, `pending`, `approved`, `rejected`, `paused`, `disabled`, `deleted`; any other Meta code is shown as Meta words it |
| Free-tier monthly limit | 0 means no limit |

## Caps and sizes

| Limit | Value |
|---|---|
| Rows per page (conversations, messages, templates) | 50 |
| Buttons per template | 10 — at most 2 links and 1 call; label up to 25 characters; quick replies kept together (Meta's rule) |
| Maximum rows a paginated request may ask for | 500 |
| Conversations per contact | 1 — the ingest upserts by contact |
| Live messages per `wa_message_id` and hub | 1 — unique index, both ingestion doors absorb the repeat (whatsapp_inbox#30) |

## Permissions per action

| To do this | You need |
|---|---|
| See conversations and messages | `whatsapp_inbox.view_conversation` |
| Assign a conversation; list, create, update or delete templates; read the monthly usage | `whatsapp_inbox.manage_settings` |
| Ingest a message | `whatsapp_inbox.manage_connections` |

By role:

- **admin** — everything.
- **manager** and **employee** — read conversations and their threads. **Cannot** assign a
  conversation, cannot see templates, cannot see or change the settings, cannot ingest, cannot
  delete.

## Dependencies

**`customers` is required** and installed with the module, but referenced softly — through its public
queries, with no foreign key.

**Nothing depends on this module.** It listens to the core event `hub.whatsapp.message_received`
and to `customers`' `customer.created` / `customer.updated` (to link a conversation to her card).

## When something looks wrong

**"I cannot find the WhatsApp requests."** They were retired (#206): nothing fed them. A booking
asked for over WhatsApp lands in Appointments or Reservations through the recipes in Automations,
and one waiting for a person is confirmed there.

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
flow's notify step. The old auto-reply settings, which nothing ever sent, were retired (#127).

**"I cannot find the greeting or out-of-hours text."** They are gone from Settings on purpose
(#127): nothing ever sent them. An automatic reply is written in the flow that answers, in
Automations.

**"A manager cannot see the templates."** Correct — templates are behind the settings permission,
which is admin-only.

**"A manager cannot assign a conversation."** Also correct, and for the same reason.

**"Meta approved my template and the hub still says pending."** The verdict is refreshed when the
Templates tab opens. If a notice says Meta could not be reached, open the tab again later.

**"I deleted a template in WhatsApp Manager and it is still in the list."** It stays, marked
«Deleted in WhatsApp Manager», so the text is not lost: nothing that uses it will be sent. Delete it
in the tab, or write a new one with a different name. The mark needs a fresh answer from Meta that
lists at least one template; with no WhatsApp number connected nothing is marked.

**"A template I created in WhatsApp Manager is not in the list."** Open the Templates tab: it is
brought in with its text, its media header kind and its quick reply, link and call buttons (#180).
Plain buttons are edited here since #185. A template with a media header, or with a link button that
carries a variable (`…/{{1}}`), is read-only here: change its wording in WhatsApp Manager («Guardar»
would register it at Meta without them).
One with named variables (`{{name}}` instead of `{{1}}`) is edited here like any other (#196): on
«Guardar» each name keeps its example, and a name you add is its own example. If it uses a carousel,
a limited-time offer, a copy-code or Flow button, a location header or a variable in the header, it
is named in a notice above the table instead; manage it in WhatsApp Manager. If you deleted it here before, it is not brought back.

**"A photo or voice note says it cannot be shown here yet."** WhatsApp sends an attachment's id,
not the file, and the hub fetches it through the platform. Until the hub offers that door
(ERPlora/hub#2114, with the platform's half in ERPlora/saas#2285) the thread names what arrived
(«Photo», «Voice note», the document's name and the caption) and you see the file on the phone.
WhatsApp only keeps an attachment for a limited time; an old one can fail with «Could not load the
attachment» for good.

**"This device cannot play it."** WhatsApp records voice notes as OGG/Opus, a format Safari on
iPhone, iPad and older Macs does not play. The thread says so and offers the file for download
instead of showing a player that stays silent; open it with another app, or listen on Chrome or the
phone's WhatsApp. The same happens with a video in a format the device does not play.

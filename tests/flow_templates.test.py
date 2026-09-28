#!/usr/bin/env python3
"""The flow templates in `flows/` have to be REAL: valid documents, exact grants, no typos (pm#112).

A flow template is the one artefact in this repo that nothing else checks. It is not compiled, it
is not packed into the module zip (see `flows/README.md`) and the runtime only sees it the day
somebody pastes it into `PUT /api/hub/flows`. So the ways it can be wrong are all silent, and all
of them surface at 3 AM in front of a customer:

1. **The document does not parse** → `PUT /api/hub/flows` refuses it and the salon has no
   automation. Checked against `hub/schemas/flow.schema.json`, the contract the hub itself serves.
2. **The grants do not match the document** → the flow saves, arms its trigger, runs, and dies on
   the first step that needed a grant nobody wrote down (`flow.grant_denied`). Every `ai` tool
   needs its `query`/`command` grant; every `notify` step needs BOTH a `notify` grant for its
   channel and a `recipient_query` grant for its exact `<query>#<field>` pair — they are two
   separate questions on purpose (hub#821). The check runs both ways: a grant that no step uses is
   an authorisation the owner was asked for and nobody spends.
3. **A query or command does not exist** → same silence, one layer down. Checked against the real
   manifests of the workspace when it is there.
4. **A parameter is not in the vocabulary of the query it addresses** — the failure this
   battery was blind to. A list query accepts `limit/offset/search/sort/dir`, `f_<col>` for each
   declared filter (`f_<col>_from`/`_to` when the filter is a `range`), the `:name` binds its own
   SQL references, and the properties of its `schema`. Anything else is not a filter: before
   hub#1201 the engine DROPPED it in silence and `queries::execute` answered `200 ok` with the
   WHOLE list, so a `notify` step resolving its recipient through that query died on
   `recipient_ambiguous` the moment the hub held a second conversation (`recipient_of` has
   refused several rows since hub#821 — with exactly one it only worked by luck, because the
   sender's just-upserted conversation WAS the list); since hub#1201 the same call is refused
   with `unknown_filter` before the read runs. Both readings kill the acknowledgement, and
   neither shows up in the document, in the grants or in the names — every name involved exists.
5. **The translations drift.** `*.en.flow.json` is the source and `*.es.flow.json` is what ships
   with the Spanish blueprint. If they stop being the same automation — a tool added to one, a step
   renamed in the other — then «the Spanish one» quietly became a different product. Only the human
   text may differ.
6. **A step's `policy` does not match what its commands DO** → either a write runs unattended
   (`auto`), or the automation is split in two steps to dodge a problem hub#1595 already solved and
   every incoming message pays an extra metered AI turn (whatsapp_inbox#55). Both are judged with
   the hub's own classification, copied into `command_only_answers`.
7. **A tool is handed over that the prompt never orders, a value is ordered that the command's
   schema refuses, or `max_iters` is past what the hub accepts** (whatsapp_inbox#61) — each a
   template that reads right and fails somewhere else: a grant nobody spends, a proposal the hub
   refuses AFTER the salon approved it, a document no hub saves.

And because these rules only ever run over documents that are already correct, the battery mutates
its OWN rules first (`self_check`) — a blinded rule would otherwise stay green forever.

Usage: tests/flow_templates.test.py   (exit 0 = green)
"""

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
FLOWS_DIR = MODULE_DIR / "flows"
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())

# The hub checkout the schema comes from. The gate DECLARES one in `ERPLORA_HUB_DIR` (the full hub
# its `module-sdk` step brings down, module-toolkit#146) and a declared hub always wins; otherwise it
# is the monorepo sibling. A CI runner only clones this repo, so before whatsapp_inbox#214 the
# sibling was never there and the layer SKIPPED on every pull request, green. Now a declared hub
# without the schema, or a CI run with no hub at all, is RED; only a bare local clone skips loudly.
HUB_DECLARED = os.environ.get("ERPLORA_HUB_DIR", "").strip()
HUB_SCHEMA = (
    pathlib.Path(HUB_DECLARED) if HUB_DECLARED else MODULE_DIR.parents[2] / "hub"
) / "schemas" / "flow.schema.json"
SCHEMA_REQUIRED = bool(HUB_DECLARED) or bool(os.environ.get("CI", "").strip())
WORKSPACE_MODULES = MODULE_DIR.parent


def flow_documents():
    return sorted(FLOWS_DIR.glob("*.flow.json"))


def grants_of(doc_path):
    """The `.grants.json` that travels with a document (one per template family)."""
    family = doc_path.name.split(".")[0]
    return FLOWS_DIR / f"{family}.grants.json"


def family_of(name):
    """The family a document belongs to: its file name without language or extension."""
    return name.split(".")[0]


# Which families run with NOBODY watching (whatsapp_inbox#58), as a LEDGER rather than a suffix in
# the file name (whatsapp_inbox#124).
#
# It used to be `-unattended` at the end of the family name, and the reason given was sound as far
# as it went: the document has nowhere to put the flag, because the hub's `flow.schema.json` is
# `additionalProperties: false` at the root, so an invented `"unattended": true` would be REFUSED
# by `PUT /api/hub/flows`. What made it stop working is that the suffix was doing a SECOND job it
# was never suited for — telling two shipped recipes apart. There were two of each: one that parked
# the booking at a person and one that did not, for a single decision the business had already
# taken in Citas («confirm automatically» on or off). The owner had to guess which card was theirs,
# every fix had to be made twice (whatsapp_inbox#100/#107, #103/#105), and the one named «without
# review» told the customer she was booked while the appointment was born waiting for a review.
#
# So the suffix is gone and the family name is the plain use — which is also what the hub route
# behind the WhatsApp card activates (whatsapp_inbox#123). What is left is this table, and it is
# anchored in BOTH directions by `unattended_ledger_problems`: a family in `flows/` that is not
# named here is one no unattended rule holds, and a row here with no family in `flows/` is a
# promise nothing keeps.
UNATTENDED_FAMILIES = frozenset(
    {
        "appointment-from-whatsapp",
        "reservation-from-whatsapp",
        # whatsapp_inbox#125. It books nothing, but it SENDS with nobody watching, which is what
        # this table is read for: a family missing from it is one `policy_problems` would start
        # calling a defect the day somebody gave it a write.
        "appointment-confirmed-to-whatsapp",
    }
)


def is_unattended(name):
    """Does this document belong to a family that books with nobody watching?"""
    return family_of(name) in UNATTENDED_FAMILIES


def unattended_ledger_problems(name, doc, families):
    """`UNATTENDED_FAMILIES` and `flows/` say the same thing — read both ways.

    A ledger rule, like `shipped_recipe_problems`, and for the same reason: what it judges is what
    is NOT there, so it cannot be a rule that reads a document. Both halves have teeth.

    * **A family in `flows/` that the table does not name** is a recipe every unattended rule goes
      quiet over — `unattended_problems` stops holding it to `policy: auto`, `hour_choice_problems`
      stops demanding the sentence that keeps the model from picking the hour, and
      `policy_problems` starts calling its writes a defect. A shipped recipe nobody classified is
      the shape whatsapp_inbox#58 spent an issue on.
    * **A row with no family in `flows/`** is the mirror: the table grows a name, every rule keyed
      off it stays green because there is no document to judge, and the business the row was added
      for has nothing to install.
    """
    problems = []
    for family in sorted(families):
        if family in UNATTENDED_FAMILIES:
            continue
        problems.append(
            f"{name}: `flows/` ships the family `{family}` and `UNATTENDED_FAMILIES` does not "
            f"name it. Every rule that asks «is anybody watching?» reads that table, so an "
            f"unnamed family is one nothing holds to `policy: auto`, to the hour rule or to the "
            f"wording it owes the customer — and `policy_problems` reports its writes as a defect "
            f"instead. Name it, or take the recipe out of `flows/`"
        )
    for family in sorted(UNATTENDED_FAMILIES):
        if family in families:
            continue
        problems.append(
            f"{name}: `UNATTENDED_FAMILIES` names `{family}` and no document in `flows/` belongs "
            f"to it. The row makes every rule keyed off it vacuously green, and the business it "
            f"was written for has no recipe to install"
        )
    return problems


# What each family WAITS FOR, as a ledger (whatsapp_inbox#125).
#
# This used to be one line at the bottom of `main()`: every document had to trigger on
# `hub.whatsapp.message_received`, and the reason given was right as far as it went — «a template
# that listens to something else is a different product wearing the same file name». What made it
# stop working is that this module now ships a recipe that legitimately waits on something else:
# the salon accepting an appointment in the diary (whatsapp_inbox#125). A blanket check has exactly
# two endings there and both are bad — it fails a correct document, or somebody deletes it and
# every document is then free to listen to anything at all.
#
# So the demand is written PER FAMILY instead of once for all of them, and it is anchored in BOTH
# directions like `UNATTENDED_FAMILIES`: a family in `flows/` with no row is a recipe nothing holds
# to its trigger, and a row with no family is a promise nothing keeps.
FAMILY_TRIGGERS = {
    "appointment-from-whatsapp": "hub.whatsapp.message_received",
    "reservation-from-whatsapp": "hub.whatsapp.message_received",
    # whatsapp_inbox#125. Not a message coming IN — the diary saying the salon accepted one. It is
    # the other half of `appointment-from-whatsapp`: that recipe tells a customer whose appointment
    # was born `pending` that «the salon will confirm shortly», and until this one shipped nothing
    # ever did. She was left watching a chat that had gone quiet for good.
    "appointment-confirmed-to-whatsapp": "appointments.appointment.confirmed",
}


def family_trigger_problems(name, doc, families):
    """Each family waits for what its row says, and every family has a row — read both ways."""
    problems = []
    for family in sorted(families - set(FAMILY_TRIGGERS)):
        problems.append(
            f"{name}: `flows/` ships the family `{family}` and `FAMILY_TRIGGERS` does not name "
            f"it, so nothing here says what it is allowed to wake up for. A recipe that quietly "
            f"changes the event it listens to is a different product wearing the same file name, "
            f"and the owner who turned the card on is never told. Name it, or take it out"
        )
    for family in sorted(set(FAMILY_TRIGGERS) - families):
        problems.append(
            f"{name}: `FAMILY_TRIGGERS` names `{family}` and no document in `flows/` belongs to "
            f"it: the row guards nothing and reads as if it did"
        )

    want = FAMILY_TRIGGERS.get(family_of(name))
    if want is None:
        return problems  # already reported above; judging it against nothing would say nothing
    events = {t.get("event") for t in doc.get("triggers", []) if t.get("kind") == "event"}
    if events != {want}:
        problems.append(
            f"{name} wakes up for {sorted(e for e in events if e)} and its family is declared to "
            f"wait on `{want}`. A document that listens to something else does not fail: it runs "
            f"at a moment nobody designed it for, spending the same grants over the wrong data — "
            f"and one that listens to something MORE runs twice"
        )
    return problems


# The chain whatsapp_inbox#125 is about: the salon accepts an appointment in the diary, and the
# customer has to hear about it on the phone she wrote from.
CONFIRMATION_TRIGGER = "appointments.appointment.confirmed"
APPOINTMENT_READ = "appointments.appointments.get"
CONVERSATIONS_READ = "whatsapp_inbox.conversations.list"
CONFIRMED_ID = "input.appointment_id"
# The one field of the diary that says where to write to her, and the filter that carries it.
DIARY_PHONE = "customer_phone"
PHONE_FILTER = "f_contact_phone"
# The contract key a `result: "first"` read always answers with, row or no row (`flows/query.rs`):
# it is the ONLY thing that tells this family apart from a run whose appointment vanished.
READ_FOUND = "found"
# whatsapp_inbox#146 — the two columns `appointments.appointments.get` answers with the day and the
# hour ALREADY READABLE, in the business's language and zone (appointments#151, first published in
# 1.1.77). They arrive split on purpose: the connector («… a las …» / «… at …») is prose, and prose
# lives in each language's own text (ADR-0055).
WHEN_DATE = "start_date_label"
WHEN_TIME = "start_time_label"


def confirmation_notice_problems(name, doc):
    """The salon confirms, and the CUSTOMER is told — to the number the DIARY holds.

    Four marks, and each one is a way the same silence comes back.

    1. **Something is actually sent.** This is whatsapp_inbox#125 word for word: the salon taps
       «Confirm» in the Agenda and nothing reaches her. A family that wakes on the confirmation
       and sends no `notify` is the bug with a file around it.
    2. **The appointment is READ first.** The event carries `appointment_id` and nothing else
       (`commands.rs` posts the command's own binds to the outbox, and `appointment_id.json` is
       `additionalProperties: false` with that one property), so the phone number does not travel
       with it. It lives in the diary, and the only step that can fetch it is a `kind: query` on
       `appointments.appointments.get`.
    3. **She is addressed by THAT phone.** The number the appointment was booked under is the one
       the salon holds for her; anything else is a guess about who this run is about.
    4. 🔴 **And the run stops when the diary has no phone for her.** `contact_phone` is declared
       `op: like` (`module.json`), so an EMPTY value goes out as `%%` and matches every
       conversation in the inbox — the lookup answers `found: true` and the first stranger in the
       list is either written to or, if the kernel notices the ambiguity, the run dies with
       `flow.recipient_ambiguous` for a reason nobody can read. A guard that only asks `found` is
       green over both. The `neq: ""` is what makes «we have no number for her» end the run
       quietly, which is the flow working, and it is the only thing standing between a walk-in
       booked by phone and a confirmation sent to somebody else's chat.
    """
    if CONFIRMATION_TRIGGER not in {
        t.get("event") for t in doc.get("triggers", []) if t.get("kind") == "event"
    }:
        # A document that waits on something else is not this rule's business. Said here rather
        # than falling out of the loops below, where «no notify» and «not this family» would be
        # the same expression and only one of them is a defect.
        return []

    steps = doc.get("steps", [])
    problems = []

    readers = [
        s
        for s in steps
        if s.get("kind") == "query" and s.get("query") == APPOINTMENT_READ
    ]
    if not readers:
        problems.append(
            f"{name} wakes up when the salon confirms an appointment and no `kind: query` step "
            f"reads `{APPOINTMENT_READ}`: the event carries `appointment_id` and nothing else, so "
            f"the customer's phone number, the service and the professional are not in this run "
            f"at all. There is nothing to write to her with, and nothing to write to her"
        )
    for reader in readers:
        params = reader.get("params") or {}
        if params.get("appointment_id") != CONFIRMED_ID:
            problems.append(
                f"{name} step `{reader.get('id')}` reads `{APPOINTMENT_READ}` with "
                f"`appointment_id` = {params.get('appointment_id')!r} instead of "
                f"`{CONFIRMED_ID}`: the appointment this run is about is the one the event named, "
                f"and any other id is a different customer's diary read out to whoever this run "
                f"reaches"
            )

    notifies = [s for s in steps if s.get("kind") == "notify"]
    if not notifies:
        problems.append(
            f"{name} wakes up when the salon confirms an appointment and never sends anything: "
            f"that IS whatsapp_inbox#125 — she asked on WhatsApp, was told the salon would "
            f"confirm shortly, the salon confirmed, and the chat stayed quiet. A recipe that "
            f"listens and says nothing is worse than no recipe: the card reads «on»"
        )

    phones = {f"steps.{r.get('id')}.{DIARY_PHONE}" for r in readers}
    for notify in notifies:
        to = notify.get("to") or {}
        sent = (to.get("params") or {}).get(PHONE_FILTER)
        if to.get("query") != CONVERSATIONS_READ or sent not in phones:
            problems.append(
                f"{name} step `{notify.get('id')}` addresses its message through "
                f"`{to.get('query')}` / `{PHONE_FILTER}` = {sent!r}, and not through "
                f"`{CONVERSATIONS_READ}` keyed on {sorted(phones) or 'the appointment read'}: the "
                f"number the appointment was booked under is the only one in this run the salon "
                f"vouched for. Anything else picks the conversation by something the salon never "
                f"said was hers"
            )

    guarded = {
        path
        for step in steps
        if step.get("kind") == "condition"
        for path, clause in (step.get("when") or {}).items()
        if isinstance(clause, dict) and clause.get("neq") == ""
    }
    # Mark 5 — the SAME trap, reached by `null` instead of by `""`, and the `neq` does not see it.
    found_guarded = {
        path
        for step in steps
        if step.get("kind") == "condition"
        for path, clause in (step.get("when") or {}).items()
        if isinstance(clause, dict) and clause.get("eq") is True
    }
    for reader in readers:
        found = f"steps.{reader.get('id')}.{READ_FOUND}"
        if found in found_guarded:
            continue
        problems.append(
            f"{name} step `{reader.get('id')}` reads the appointment and no `condition` demands "
            f"`{{\"{found}\": {{\"eq\": true}}}}`: when the read finds NO row — the appointment "
            f"was deleted between the confirmation and the run, and the outbox delivers "
            f"at-least-once — `result: first` still answers, only without the row's fields. A path "
            f"that resolves to nothing is `null` (`flows/def.rs::resolve`), `json_eq(null, \"\")` "
            f"is false, so the `neq: \"\"` guard above answers TRUE and lets the run through. The "
            f"phone then travels as `null`, which the list engine treats as ABSENT "
            f"(`queries.rs`: `p.get(k).is_some_and(|v| !v.is_null())`), the filter is dropped "
            f"altogether and `{CONVERSATIONS_READ}` answers the first conversation of the hub. It "
            f"is the `%%` of mark 4 by another road: `flow.recipient_ambiguous` where there are "
            f"several chats, and a confirmation with an empty service and an empty professional "
            f"delivered to the wrong customer where there is one"
        )
    for path in sorted(phones - guarded):
        problems.append(
            f"{name} sends to `{PHONE_FILTER}` = `{path}` and no `condition` step demands "
            f"`{{\"{path}\": {{\"neq\": \"\"}}}}`: `contact_phone` is declared `op: like`, "
            f"so an appointment the salon booked over the counter — no phone on the card — goes "
            f"out as `%%` and matches EVERY conversation in the inbox. The lookup answers "
            f"`found: true` and the confirmation is delivered to a stranger, or the run dies with "
            f"`flow.recipient_ambiguous` and nobody can read why. Asking `found` alone is green "
            f"over both"
        )

    # Mark 6 — whatsapp_inbox#146: the message says WHEN. Skipped with no reader, because then
    # there is nothing to name the hour from and mark 2 already said so.
    if readers:
        for notify in notifies:
            text = (notify.get("vars") or {}).get("text")
            placeholders = set(
                re.findall(r"\{\{\s*([^{}]+?)\s*\}\}", text if isinstance(text, str) else "")
            )
            missing = [
                label
                for label in (WHEN_DATE, WHEN_TIME)
                if not any(f"steps.{r.get('id')}.{label}" in placeholders for r in readers)
            ]
            if missing:
                problems.append(
                    f"{name} step `{notify.get('id')}` confirms the appointment without "
                    f"{' or '.join(f'`{{{{steps.<read>.{m}}}}}`' for m in missing)} in its text: "
                    f"she just asked for an appointment and the one thing she needs to know — the "
                    f"day and the hour she has to come — is the one the message leaves out "
                    f"(whatsapp_inbox#146). `{APPOINTMENT_READ}` answers both already readable, in "
                    f"the business's language and zone; the raw `start_datetime` is an ISO instant "
                    f"the mapping language cannot format"
                )
    return problems


def needed_grants(doc):
    """Exactly the grants this document needs, as `(kind, value)` pairs.

    A model is not the only thing that spends a grant, and this used to read as if it were. The
    DETERMINISTIC steps go through the very same gates — `crates/runtime/src/flows/grants.rs`
    puts `kind: query` (hub#954) through `check_query_grant` and `kind: command` through
    `check_command_grant`, the same two doors the `ai` step's tools use — so a document whose
    only reader is a `query` step needed a grant this function said nobody needed. Both
    directions of the comparison lied because of it: the missing grant was never demanded, and
    the grant that IS spent was reported as «an authorisation nobody spends» and invited to be
    deleted, which would have taken the step down with `flow.grant_denied` on the first run
    (whatsapp_inbox#103).

    `kind: http` is deliberately absent: its grant is a URL PATTERN and the step carries a
    templated URL, so what it needs cannot be derived from the document — `allows_http` decides
    that against the URL as really built. A template that adds an `http` step has to bring its
    own rule.
    """
    needed = set()
    for step in doc.get("steps", []):
        kind = step.get("kind")
        if kind == "ai":
            tools = step.get("tools", {})
            for q in tools.get("queries", []):
                needed.add(("query", q))
            for c in tools.get("commands", []):
                needed.add(("command", c))
        elif kind == "query":
            needed.add(("query", step["query"]))
        elif kind == "command":
            needed.add(("command", step["command"]))
        elif kind == "notify":
            needed.add(("notify", step["channel"]))
            to = step["to"]
            needed.add(("recipient_query", f"{to['query']}#{to['field']}"))
    return needed


def declared_grants(path):
    body = json.loads(path.read_text())
    items = body["grants"] if isinstance(body, dict) else body
    return {(g["kind"], g["value"]) for g in items}


def declared_command_pins(path):
    """`command -> the payload fields its grant FIXES`, `{}` for a grant that fixes none.

    Deliberately NOT part of `declared_grants`: that one answers «is this authorisation asked
    for», and the pin does not change the answer — the hub's own identity for a grant row is
    `(hub, flow, kind, value)` and the pin is a column of it, so folding it into the pair would
    turn «the same grant, narrowed» into «a grant nobody asked for» in both directions of the
    comparison `main()` runs.
    """
    body = json.loads(path.read_text())
    items = body["grants"] if isinstance(body, dict) else body
    return {
        g["value"]: (g.get("payload") or {}) for g in items if g.get("kind") == "command"
    }


def workspace_manifests():
    """`(module_dir, manifest)` for this module and every SIBLING next to it, or None if bare.

    🔴 `WORKSPACE_MODULES.is_dir()` is NOT the question. This module is always inside SOME
    directory, so that probe answers True everywhere — on a CI runner it is
    `/home/runner/work/whatsapp_inbox/`, holding exactly one module: ours. The glob then found one
    manifest, and every cross-module name in the templates (`appointments.*`, `customers.*`,
    `staff.*`, `services.*`, `schedules.*`) was reported as «no installed module declares it»: 22
    FAILs on a battery whose job is to check GRANTS, and the module's gate red on a runner that is
    simply not the monorepo (whatsapp_inbox#31).

    The real question is whether the SIBLINGS are there. A workspace is a directory holding modules
    OTHER than this one; anything else is a bare checkout, and the check has to skip loudly rather
    than fail for something the templates did not do wrong.

    Order matters for the callers that resolve a name to ONE definition. The workspace also holds
    the fleet's worktrees (`appointments-wt-89`, `cash_register-wt-61`…), which declare the same
    query ids as the module they branch from while being mid-edit. A directory whose NAME is the
    manifest's `id` is the module's own checkout; anything else is a worktree, and it only answers
    for a name no canonical checkout claims. Ours goes last and beats everyone: this battery
    verifies THIS checkout, not the one next door.
    """
    if not WORKSPACE_MODULES.is_dir():
        return None
    worktrees, canonical = [], []
    for manifest in sorted(WORKSPACE_MODULES.glob("*/module.json")):
        if manifest.parent == MODULE_DIR:
            continue
        try:
            m = json.loads(manifest.read_text())
        except json.JSONDecodeError:
            continue
        target = canonical if manifest.parent.name == m.get("id") else worktrees
        target.append((manifest.parent, m))
    if not worktrees and not canonical:
        return None
    return worktrees + canonical + [(MODULE_DIR, MANIFEST)]


def resolved_modules(manifests):
    """`module id -> (module_dir, manifest)` — ONE answer per module, never a union.

    🔴 The union was the hole this battery was blind through, and it is measured. On 2026-09-06 the
    workspace held BOTH `appointments/` (the canonical checkout, 13 releases stale at 1.1.56, where
    `appointments.availability.slots` is still a `query`) and `appointments-wt-132/` (a fleet
    worktree at 1.1.69, where the same name is a `command`). Unioning every manifest it found made
    the name a query AND a command at once, so layer 3 — the layer whose whole job is «does this
    operation exist with THIS kind» — answered yes to both readings and the templates went green
    while the flow was, in production, silently losing the tool (whatsapp_inbox#52).

    A workspace answers with the precedence `workspace_manifests` already establishes: a directory
    whose name IS the manifest's id is the module's own checkout and wins; a worktree only answers
    for an id no canonical checkout claims; ours goes last and beats everyone.
    """
    out = {}
    for module_dir, m in manifests:
        mid = m.get("id")
        if isinstance(mid, str) and mid:
            out[mid] = (module_dir, m)
    return out


def copies_of(manifests, module_id):
    """Every checkout in the workspace that claims `module_id`, newest first."""
    found = [(d, m) for d, m in manifests if m.get("id") == module_id]
    return sorted(found, key=lambda dm: version_tuple(dm[1].get("version")) or (), reverse=True)


def workspace_contracts(resolved):
    """Every query and command name the workspace declares — our own included."""
    queries, commands = set(), set()
    for _, m in resolved.values():
        queries |= set(m.get("queries") or {})
        commands |= set(m.get("commands") or {})
    return queries, commands


def query_definitions(resolved):
    """`query id -> (module_dir, definition)`, from the one manifest per module id."""
    out = {}
    for module_dir, m in resolved.values():
        for qid, qdef in (m.get("queries") or {}).items():
            if isinstance(qdef, dict):
                out[qid] = (module_dir, qdef)
    return out


def command_definitions(resolved):
    """`command id -> (module_dir, definition)`, from the one manifest per module id."""
    out = {}
    for module_dir, m in resolved.values():
        for cid, cdef in (m.get("commands") or {}).items():
            if isinstance(cdef, dict):
                out[cid] = (module_dir, cdef)
    return out


def sql_binds(sql):
    """Every `:name` a SQL statement references, read the way the runtime reads it.

    Mirrors `crates/runtime/src/queries.rs::all_binds` + `code_spans`: `::` is a Postgres cast and
    never a bind, and `'…'` literals, `-- …` and `/* … */` are text, not code. The last part is not
    a nicety — `queries/conversations_list.sql` documents `:status`, `:search` and `:assigned_to_id`
    in a COMMENT, and a reader that counted those would hand three names the engine never binds to
    the vocabulary below, turning this whole layer into a check that passes.
    """
    out, i, n = [], 0, len(sql)
    while i < n:
        c = sql[i]
        if c == "'":  # string literal — verbatim until it closes
            i += 1
            while i < n and sql[i] != "'":
                i += 1
            i += 1
        elif c == "-" and sql[i + 1 : i + 2] == "-":
            i = sql.find("\n", i)
            i = n if i == -1 else i
        elif c == "/" and sql[i + 1 : i + 2] == "*":
            end = sql.find("*/", i + 2)
            i = n if end == -1 else end + 2
        elif c == ":":
            if sql[i + 1 : i + 2] == ":":  # `::` cast
                i += 2
                continue
            j = i + 1
            while j < n and (sql[j].isalnum() or sql[j] == "_"):
                j += 1
            if j > i + 1:
                name = sql[i + 1 : j]
                if name not in out:
                    out.append(name)
            i = max(j, i + 1)
        else:
            i += 1
    return out


def query_vocabulary(module_dir, qdef):
    """The parameter names a query ACCEPTS, or None when they cannot be established.

    The three places a query declares something callable, exactly as
    `crates/runtime/src/queries.rs::accepted_params` composes them:

    * the list engine's own words — `limit`, `offset`, `search`, `sort`, `dir`;
    * one name per declared filter, always under the `f_` prefix — `f_<col>`, and `f_<col>_from` /
      `f_<col>_to` when the filter is a `range`;
    * every `:name` bind of its SQL, plus the properties of its `schema` when it declares one.

    A query with no `list` block is not paginated and has no filters: its vocabulary is its binds
    and its schema, nothing more.
    """
    accepted = set()

    sql = qdef.get("sql")
    if isinstance(sql, str):
        if sql.strip().endswith(".sql"):
            path = module_dir / sql
            if not path.is_file():
                return None
            sql = path.read_text()
        accepted |= set(sql_binds(sql))

    spec = qdef.get("list")
    if isinstance(spec, dict):
        accepted |= {"limit", "offset", "search", "sort", "dir"}
        for col, f in (spec.get("filters") or {}).items():
            if (f or {}).get("op") == "range":
                accepted |= {f"f_{col}_from", f"f_{col}_to"}
            else:
                accepted.add(f"f_{col}")

    schema_rel = qdef.get("schema")
    if isinstance(schema_rel, str):
        path = module_dir / schema_rel
        if not path.is_file():
            return None
        try:
            props = json.loads(path.read_text()).get("properties") or {}
        except json.JSONDecodeError:
            return None
        accepted |= set(props)

    return accepted


def floors_of(doc_path):
    """The `.requires.json` that travels with a document — the version floor of what it consumes."""
    family = doc_path.name.split(".")[0]
    return FLOWS_DIR / f"{family}.requires.json"


def version_tuple(raw):
    """`"1.1.69"` -> `(1, 1, 69)`, or None when it is not a plain dotted number."""
    if not isinstance(raw, str):
        return None
    parts = []
    for chunk in raw.split("."):
        digits = ""
        for ch in chunk:
            if not ch.isdigit():
                break
            digits += ch
        if not digits:
            return None
        parts.append(int(digits))
    return tuple(parts) if parts else None


def module_read_permissions(resolved):
    """`command id -> the permissions the OWNING module also asks of its own queries`.

    The half that makes the classification below safe, and the module states it by handing out its
    own permissions rather than the core guessing from names (hub#1594). It is read off the SAME
    manifest the command lives in on purpose: what another module happens to call `view_*` says
    nothing about this one.
    """
    out = {}
    for _, m in resolved.values():
        perms = {
            q.get("permission")
            for q in (m.get("queries") or {}).values()
            if isinstance(q, dict) and isinstance(q.get("permission"), str)
        }
        for cid in m.get("commands") or {}:
            out[cid] = perms
    return out


def command_only_answers(cdef, read_permissions):
    """Does this command ANSWER a question rather than change the business?

    This is `assistant::command_only_answers` (hub#1595) read off the manifest instead of the
    registry, and being a COPY is the point: the hub decides this at runtime and the flow runner
    reads its verdict off the tool spec, so a battery that decided it by its OWN rule would go
    green on a document the hub then treats differently. Five signals from the owner's manifest,
    and ALL of them have to hold:

    * a declared `risk` that is not `normal` wins over everything else — a manifest that
      contradicts itself is resolved on the safe side;
    * no `sql` and no `emit` — a state change the rest of the hub has to hear about is a write by
      definition;
    * no `min_affected_rows` and no `expect_rows` — both of them count ROWS CHANGED;
    * and its `permission` is one the owning module also asks of its own QUERIES.

    That last signal is what replaced the `view_` prefix this battery used to read, and the
    difference is not cosmetic: a prefix is a naming habit nobody enforces, while «the module hands
    this permission to its own reads» is a statement the module makes. `customers.bulk_create`
    declares no `emit` and would have walked through the old rule the day somebody named its
    permission `view_something`; it cannot walk through this one, because no query of `customers`
    is paid for with it.

    The absence of a signal is read as a WRITE, never as a read.
    """
    ai = cdef.get("ai")
    risk = ai.get("risk") if isinstance(ai, dict) else None
    if risk is not None and risk != "normal":
        return False
    if cdef.get("sql") or cdef.get("emit"):
        return False
    if cdef.get("min_affected_rows") is not None or cdef.get("expect_rows") is not None:
        return False
    permission = cdef.get("permission")
    if not isinstance(permission, str):
        return False
    return permission in (read_permissions or set())


def quoted_steps(doc, worked_from=False):
    """Step ids that some OTHER step interpolates (`{{steps.<id>.…}}`) — who feeds whom.

    Read the way the hub reads it (`flows::def::render_template`): every `{{ … }}` pair, the path
    TRIMMED before it is resolved. So `{{ steps.look.text }}` names `look` exactly as
    `{{steps.look.text}}` does — a guard that only knew the unspaced spelling let the two-step
    workaround back in with one space.

    `worked_from=True` asks the narrower question the two-step rule needs: who quotes it **to work
    from it**. A `notify` quoting a step is the DELIVERY — the words going to the customer, which
    is what the step that wrote them is for — and counting it made the rule refuse the only shape
    the attended family has for offering slots (whatsapp_inbox#109): there the step that books can
    never declare `output`, so the step that writes the message is the one that looks them up, and
    a `notify` sends its words. Every other kind still counts: a `command` or an `ai` step reading
    another step's PROSE is exactly the handoff where the ids and the minutes get lost.
    """
    out = set()
    for step in doc.get("steps", []):
        if worked_from and step.get("kind") == "notify":
            continue
        for path in quoted_paths(step):
            quoted = path[len("steps.") :].split(".")[0].strip()
            if quoted and quoted != step.get("id"):
                out.add(quoted)
    return out


def quoted_paths(step):
    """Every `{{ … }}` path ONE step interpolates, trimmed the way the hub trims it, `steps.…` only."""
    out = set()
    rest = json.dumps(step, ensure_ascii=False)
    while True:
        start = rest.find("{{")
        if start < 0:
            break
        after = rest[start + 2 :]
        end = after.find("}}")
        if end < 0:
            break
        path = after[:end].strip()
        if path.startswith("steps."):
            out.add(path)
        rest = after[end + 2 :]
    return out


def ai_steps(doc):
    """`(step id, policy, [command names])` for every `ai` step that may propose a write."""
    out = []
    for step in doc.get("steps", []):
        if step.get("kind") != "ai":
            continue
        commands = ((step.get("tools") or {}).get("commands")) or []
        out.append((step.get("id"), step.get("policy") or "manual", list(commands)))
    return out


def policy_problems(name, doc, commands_def, read_perms):
    """`policy` weighed against what the commands a step declares actually DO.

    ONE direction is a defect, and it is the dangerous one: a step that runs its commands without
    asking (`policy: "auto"`) may only declare operations that answer. A write in there is the
    model booking, charging or deleting at 3 AM with nobody looking, which is the entire reason
    `manual` is the default (ADR-0283 D3).

    With ONE exception, and it is a family that says so in its own file name
    (`is_unattended`): the salon that runs unattended has nobody to look, and «the model booking
    at 3 AM with nobody looking» is precisely what it bought (whatsapp_inbox#58). The exception is
    narrow on purpose — it is not a per-step opt-out a prompt can talk itself into, it applies to
    every step of that document and to no step of any other, and `unattended_problems` charges
    that family for it by holding it to the promise the name makes.

    The opposite direction used to be a defect too, and hub#1595 retired it. Before it, `kind` was
    doing two jobs — which door of the dispatcher a call goes through AND whether a person confirms
    it — so a read published as a *command* (which is what a WASM handler is for: answering by
    crossing data another module owns) parked the QUESTION in `_flow_approvals` under `manual` and
    ended the turn. The owner opened the tray in the morning and was asked to approve «check
    availability», which is not a decision anybody can take. Today a command that only answers runs
    in the turn under ANY policy and its result goes back to the model like a query's rows, so a
    read in a `manual` step is not a defect: it is the shape that costs one metered AI turn instead
    of two.

    Which turns the old workaround into the defect this looks for instead: a step whose declared
    commands ALL only answer, and whose words another step quotes, is the automation split in two
    to dodge a problem the kernel no longer has (whatsapp_inbox#55). It bills an extra AI turn per
    incoming message, and everything the first step learned reaches the second as prose — which is
    where the ids, the offsets and the minutes get lost.
    """
    problems = []
    quoted = quoted_steps(doc, worked_from=True)
    for step_id, policy, names in ai_steps(doc):
        verdicts = []
        for cname in names:
            target = commands_def.get(cname)
            if target is None:
                continue  # already reported as a name no module declares
            _, cdef = target
            answers = command_only_answers(cdef, read_perms.get(cname))
            verdicts.append(answers)
            if policy == "auto" and not answers and not is_unattended(name):
                problems.append(
                    f"{name} step `{step_id}` declares `{cname}` in `tools.commands` "
                    f"under `policy: auto`, and that operation WRITES. `auto` runs it in "
                    f"the turn, unattended: a write with nobody looking is exactly what "
                    f"`manual` is the default for"
                )
        if verdicts and all(verdicts) and step_id in quoted:
            problems.append(
                f"{name} step `{step_id}` declares nothing but operations that ANSWER "
                f"({', '.join(sorted(names))}) and hands its findings to another step in prose. "
                f"That is the two-step workaround whatsapp_inbox#55 removed: since hub#1595 a "
                f"command that only answers runs in the turn whatever the policy says, so those "
                f"reads belong in the step that ACTS on them. Split, they cost an extra metered "
                f"AI turn per incoming message and the ids travel as words"
            )
    return problems


def writing_ai_steps(doc):
    """Indexes of the `ai` steps that can PROPOSE a write — the ones a customer waits on.

    A step that declares `output` under anything but `auto` is NOT one of them, and that is the
    kernel's own arithmetic rather than a convention of this file: a proposal ends the turn, so a
    step that owes data could never fill it, and `agent_runner.rs` refuses the proposal by name
    before the approval row exists (hub#1639). Nothing parks, so nobody can say «no» to it, so the
    rules built on this list — survive a rejection, be followed by a `notify` that carries the
    words, run `auto` where nobody is watching — have nothing to ask of it.

    Which is what lets the attended family offer slots at all (whatsapp_inbox#109): the step that
    writes the message holds the reads and hands the rows over, `manual` and unrejectable, while
    the step that PROPOSES the appointment stays the one this list is about.
    """
    out = []
    for i, step in enumerate(doc.get("steps", [])):
        if step.get("kind") != "ai":
            continue
        if step.get("output") and (step.get("policy") or "manual") != "auto":
            continue
        if ((step.get("tools") or {}).get("commands")) or []:
            out.append(i)
    return out


def silence_problems(name, doc):
    """Does the automation SAY something back to the person who wrote in, after it books?

    whatsapp_inbox#58, and it is the half of that issue that has nothing to do with who approves:
    a customer writes at 3 AM, gets «we will confirm when we open», and then — whether the salon
    approves the proposal at 9 AM or the hub books it unattended — **nobody tells them anything**.
    The appointment exists, the customer does not know. That is not a missing nicety: it is the
    automation stopping one step short of the thing it promised in its own first message.

    Mechanically: if a document has an `ai` step that can PROPOSE a write, some `notify` has to come
    AFTER it. The acknowledgement at the top does not count and that is the whole point — it is sent
    before anything happened, so it cannot say what happened. It is the LAST such step that must be
    answered: a document that tells the customer «found your record» and then books in silence has
    the same hole.

    Why this is checkable at all: the run does not end when a proposal parks. `manual` writes an
    `_flow_approvals` row and stops the turn, and when a person decides, `decide_flow_approval`
    completes the step with `IoResult::Done` and the run CARRIES ON to the next step. So a `notify`
    written after the `ai` step fires on the way out of the approval — and, when the model proposed
    nothing at all, on the way out of the step itself. One step covers both endings.

    And it has to say what HAPPENED, which only the booking step knows: `result` is `{ok, new_ids}`
    and `proposed.arguments` is an opaque string, so the day, the hour and the professional exist
    in exactly one place — the `text` that step wrote for the customer. A `notify` after the
    booking whose words are its own («Done.») is a message that cannot carry them, and it passed
    this rule until a reviewer sent it (whatsapp_inbox#58, mutant N7). Some `notify` after the
    last booking step has to carry `{{steps.<that step>.text}}`.

    ONE HOP is allowed, and it is what whatsapp_inbox#67 needs: the message can come from a step
    in between that reads how the turn ended and quotes the booking step itself (`relays_of`).
    What is not allowed is the hop losing the words on the way — a middle step that quotes nobody
    is the same «Done.» wearing an extra step.
    """
    steps = doc.get("steps", [])
    writing = writing_ai_steps(doc)
    if not writing:
        return []
    last = writing[-1]
    writer = steps[last].get("id")
    after = [s for s in steps[last + 1 :] if s.get("kind") == "notify"]
    if not after:
        return [
            f"{name} step `{writer}` can book something and NO `notify` comes after it: "
            f"the customer is told «we will confirm shortly» and then never hears again, whoever "
            f"approves. The run resumes after an approval (`decide_flow_approval` completes the step "
            f"with `Done`), so a `notify` written after this step covers both endings — booked, and "
            f"nothing found"
        ]
    speakers = {writer} | relays_of(steps, last, writer)
    if any(
        any(f"steps.{sp}.text" in quoted_paths(s) for sp in speakers) for s in after
    ):
        return []
    return [
        f"{name} step `{writer}` can book something and the `notify` after it never carries "
        f"`{{{{steps.{writer}.text}}}}`, directly or through a step that quotes it: the day, the "
        f"hour and the professional live only in the text that step wrote for the customer "
        f"(`result` is `{{ok, new_ids}}` and `proposed.arguments` is an opaque string), so a "
        f"notify with words of its own tells them nothing about what happened"
    ]


def relays_of(steps, writer_index, writer):
    """Ids of the steps after the writer that pass the writer's OWN words on.

    The one hop `silence_problems` allows, and it is the shape whatsapp_inbox#67 needs: the
    message that reaches the customer cannot be the booking text verbatim any more, because that
    text was written before anybody said yes or no. A step in between reads how the turn ended and
    writes what to send — so the `notify` quotes the relay, and the relay quotes the writer.

    One hop, not a chain: what is being protected is that the day, the hour and the professional
    survive to the customer, and a relay that never quotes the writer cannot carry them however
    many steps follow it. That is the mutant this keeps killing — a step in the middle that writes
    «Done.» of its own (whatsapp_inbox#58, reviewer mutant N7) is not a relay, it is a wall.
    """
    out = set()
    for step in steps[writer_index + 1 :]:
        sid = step.get("id")
        if sid and f"steps.{writer}.text" in quoted_paths(step):
            out.add(sid)
    return out


def mute_refusal_problems(name, doc):
    """A «no» from the salon has to reach the customer too — whatsapp_inbox#67.

    `silence_problems` covers the endings where the automation ACTED: it booked, or it proposed
    nothing. This is the third ending, and until hub#1622 it was the one nobody could write: the
    salon opens the tray at 9 AM, reads the proposal and REJECTS it. The customer, who was told at
    3 AM «we will confirm as soon as the salon opens», is never told anything. She waits for a
    message that cannot arrive, because the run is already dead — a rejection used to end it as
    `cancelled` before the `notify` was ever reached.

    Two things have to be true, and they are two halves of the same fix:

    * **the run has to survive the «no»** — the step that can be rejected declares
      `"on_reject": "continue"`. Without it the kernel cancels the run at the rejection and every
      step written after it, `notify` included, is dead code;
    * **and what goes out has to know it was a «no»** — the step whose `text` the `notify` sends
      has to read `steps.<writer>.status`. With `continue` alone the run reaches the `notify` and
      sends the booking text the model wrote BEFORE the decision: «you are booked, Tuesday at 10
      with Ana». Telling a customer she has an appointment the salon just refused is worse than
      telling her nothing, so half this fix is not a partial fix — it is a new defect.

    Only the LAST `ai` step that can write is judged, and only when it is `manual`: `auto` never
    asks anybody, so there is no «no» to survive (the `-unattended` family lives there). And only
    when a `notify` follows it — a document that says nothing to anybody is `silence_problems`.
    """
    steps = doc.get("steps", [])
    writing = writing_ai_steps(doc)
    if not writing:
        return []
    last = writing[-1]
    step = steps[last]
    if (step.get("policy") or "manual") != "manual":
        return []
    writer = step.get("id")
    after = [s for s in steps[last + 1 :] if s.get("kind") == "notify"]
    if not after:
        return []

    problems = []
    if step.get("on_reject") != "continue":
        problems.append(
            f"{name} step `{writer}` can be REJECTED (`policy: manual`) and does not declare "
            f"`\"on_reject\": \"continue\"`: a «no» ends the run as `cancelled` right there, so "
            f"the `notify` written after it never runs and the customer keeps waiting for the "
            f"answer the automation promised her"
        )

    by_id = {s.get("id"): s for s in steps}
    for notify in after:
        for path in sorted(quoted_paths(notify)):
            if not path.endswith(".text"):
                continue
            speaker = path[len("steps.") :].split(".")[0].strip()
            source = by_id.get(speaker)
            if source is not None and f"steps.{writer}.status" in quoted_paths(source):
                continue
            problems.append(
                f"{name} `notify` step `{notify.get('id')}` sends `{{{{{path}}}}}`, and "
                f"`{speaker}` never reads `{{{{steps.{writer}.status}}}}`: it cannot tell an "
                f"approved booking from a rejected one, so a customer whose appointment the salon "
                f"just refused is told the day, the hour and the professional she is NOT getting"
            )
    return problems


# The endings a status can carry that `mute_refusal_problems` does not cover, and what each of
# them costs the run when the document stays silent about it. Both keys were opened by the kernel
# for THIS hole and default to the answer that predates them, so a document that says nothing keeps
# the bug: the vocabulary is closed and `continue` is the only value that reaches the next step.
UNANSWERED_ENDINGS = (
    (
        "on_expire",
        "expired",
        "hub#1634",
        "nobody decides at all — the proposal sits in the tray until its 72 h run out and the "
        "sweep CANCELS the run",
    ),
    (
        "on_error",
        "failed",
        "hub#1635",
        "the salon approves and the WRITE breaks — somebody took the slot in between, the "
        "professional no longer works that day — and the run ends as `failed` right there",
    ),
)


def unanswered_ending_problems(name, doc):
    """The two endings left over after «booked», «nothing found» and «no» — whatsapp_inbox#70.

    `silence_problems` covers the endings where the automation ACTED, `mute_refusal_problems` the
    one where a person said no. These are the two where NOBODY said anything the customer could be
    told about, and until hub#1634/hub#1635 they were the two a document could not survive:

    * **the proposal expires** — she wrote at 3 AM, the salon never opened the tray, and 72 h later
      the sweep closes the proposal. Nothing was booked, nothing was refused, and the run is
      `cancelled` before the `notify` is reached;
    * **the salon approves and the write FAILS** — between 3 AM and 9 AM the slot went, or the
      professional stopped working that day. `decide_flow_approval` completes the step with
      `IoResult::Failed`, the tray shows the failure to the salon, and the run ends as `failed`.

    In both the customer was told «we will confirm as soon as the salon opens» and is then told
    nothing at all, for ever. Two things have to be true, and they are the same two halves
    `mute_refusal_problems` asks of a rejection:

    * **the run has to survive the ending** — the step that can park declares
      `"on_expire": "continue"` and `"on_error": "continue"`. Both keys DEFAULT to what the kernel
      always did (`reject` / `stop`), so silence here is not neutral: it is the bug;
    * **and what goes out has to KNOW which ending it was** — the step whose `text` the `notify`
      sends already reads `steps.<writer>.status` (that is `mute_refusal_problems`), and now that
      status can also read `expired` or `failed`. A prompt that was never told those two words
      reads them as neither `rejected` nor anything else it knows and takes its «nothing was
      refused» branch, which sends her, word for word, the booking the model wrote for an
      appointment that does not exist. Half this fix is a new defect, exactly as it was for the «no».

    Same gate as the rejection rule, and for the same reasons: only the LAST `ai` step that can
    write, only under `manual` — `auto` parks nothing, so there is no tray to expire and a broken
    tool call comes back to the model as a tool result rather than failing the step — and only when
    a `notify` follows it. A speaker that does not read `status` at all is `mute_refusal_problems`'s
    hole, not this one: one hole, one owner.
    """
    steps = doc.get("steps", [])
    writing = writing_ai_steps(doc)
    if not writing:
        return []
    last = writing[-1]
    step = steps[last]
    if (step.get("policy") or "manual") != "manual":
        return []
    writer = step.get("id")
    after = [s for s in steps[last + 1 :] if s.get("kind") == "notify"]
    if not after:
        return []

    # The steps that actually WRITE what she receives: quoted by a `notify` after the writer, and
    # already reading how the turn ended. Deduplicated by id — two `notify` steps sending the same
    # relay is one prompt, not two defects.
    by_id = {s.get("id"): s for s in steps}
    speakers = {}
    for notify in after:
        for path in sorted(quoted_paths(notify)):
            if not path.endswith(".text"):
                continue
            speaker = path[len("steps.") :].split(".")[0].strip()
            source = by_id.get(speaker)
            if source is not None and f"steps.{writer}.status" in quoted_paths(source):
                speakers[speaker] = source

    problems = []
    for key, word, issue, cost in UNANSWERED_ENDINGS:
        if step.get(key) != "continue":
            problems.append(
                f"{name} step `{writer}` can park a proposal (`policy: manual`) and does not "
                f'declare `"{key}": "continue"` ({issue}): {cost}, so the `notify` written after '
                f"it never runs and the customer — promised an answer «as soon as the salon "
                f"opens» — is never told anything at all"
            )
        for speaker, source in sorted(speakers.items()):
            if f"`{word}`" not in (prompt_of(source) or ""):
                problems.append(
                    f"{name} step `{speaker}` writes the message the customer receives and never "
                    f"names the `{word}` ending of `{{{{steps.{writer}.status}}}}` ({issue}): with "
                    f'`{key}` the run REACHES it, and an outcome the prompt was never told about '
                    f"falls into its «nothing was refused» branch — so she is sent, word for word, "
                    f"the booking the model wrote for an appointment that does not exist"
                )
    return problems


def assistant_failure_problems(name, doc):
    """When the ASSISTANT fails, the customer still hears from us — whatsapp_inbox#122.

    The customer writes, is told «let me check the diary, I will come straight back to you», and
    the `ai` step that was going to answer her FAILS: the SaaS proxy is down, the assistant quota
    is spent, the model's answer came back broken (`crates/server/src/agent_runner.rs` turns every
    one of those into `IoResult::Failed`). Without a policy the kernel ends the run as `failed`
    right there, and she never hears another word — the promise of the first message is the last
    thing she is told.

    A document can answer that since hub#2066 (`run_if`, first published in v1.1.30), and the shape
    is the one the hub proves in `flow_step_run_if.rs`
    (`when_the_assistant_fails_the_customer_gets_the_fallback_and_nothing_else`). For EVERY `ai`
    step a WhatsApp `notify` already spoke before — i.e. every step she is waiting on — three
    things, in this order and adjacent:

    * the step declares `"on_error": "continue"`: the failure is recorded on the step (the owner
      still reads it in the run history) and the run reaches the next step instead of dying;
    * the NEXT step is a WhatsApp `notify` to the same number the acknowledgement went to, guarded
      by `run_if: {"steps.<ai>.status": {"eq": "failed"}}`, whose words are FIXED. Fixed because
      the one step that could have written them is the one that failed: quoting any `{{…}}` there
      sends her an empty message or a placeholder;
    * the step after it is a `condition` on `{"steps.<ai>.status": {"neq": "failed"}}`: it ends
      the run when the assistant failed, so nothing written for a successful turn — a confirmation
      quoting the empty `text`, a second assistant turn billed against the quota that just ran
      out — goes out after the apology. When the assistant answered, the guarded `notify` is
      skipped and this condition lets the run carry on exactly as before.

    Adjacent on purpose: any step in between is one more thing that can fail or stop the run
    before she is told.
    """
    steps = doc.get("steps", [])
    problems = []
    acknowledged = None
    for i, step in enumerate(steps):
        if step.get("kind") == "notify" and step.get("channel") == "whatsapp":
            if acknowledged is None:
                acknowledged = step
            continue
        if step.get("kind") != "ai" or acknowledged is None:
            continue
        sid = step.get("id")
        status = f"steps.{sid}.status"
        if step.get("on_error") != "continue":
            problems.append(
                f"{name} step `{sid}` is an assistant turn the customer is waiting on and does not "
                f'declare `"on_error": "continue"`: when the assistant fails (proxy down, quota '
                f"spent, a broken answer) the run ends as `failed` there and she never hears "
                f"another word after «{(acknowledged.get('vars') or {}).get('text', '')}»"
            )
        fallback = steps[i + 1] if i + 1 < len(steps) else {}
        if not (
            fallback.get("kind") == "notify"
            and fallback.get("channel") == "whatsapp"
            and fallback.get("run_if") == {status: {"eq": "failed"}}
        ):
            problems.append(
                f"{name} step `{sid}` is not followed by a WhatsApp `notify` guarded by "
                f'`"run_if": {{"{status}": {{"eq": "failed"}}}}`: nothing tells the customer that '
                f"the automation could not answer her and that the business will"
            )
        else:
            text = str((fallback.get("vars") or {}).get("text") or "")
            if not text.strip() or "{{" in text:
                problems.append(
                    f"{name} step `{fallback.get('id')}` is the message she gets when `{sid}` "
                    f"failed, and its words are not FIXED ({text!r}): the step that could have "
                    f"written them is the one that failed, so she gets an empty message or a "
                    f"placeholder"
                )
            if fallback.get("to") != acknowledged.get("to"):
                problems.append(
                    f"{name} step `{fallback.get('id')}` does not write to the number the "
                    f"acknowledgement `{acknowledged.get('id')}` went to: the apology reaches "
                    f"somebody else, or nobody"
                )
        stop = steps[i + 2] if i + 2 < len(steps) else {}
        if not (
            stop.get("kind") == "condition"
            and (stop.get("when") or {}).get(status) == {"neq": "failed"}
        ):
            problems.append(
                f"{name} step `{sid}` fails without a `condition` on "
                f'`{{"{status}": {{"neq": "failed"}}}}` right after the apology: the run carries '
                f"on after a failed assistant turn and sends her what was written for a turn that "
                f"never happened"
            )
    return problems


def assistant_silence_problems(name, doc):
    """When the assistant ANSWERS but says nothing, the customer is told as if it had failed —
    whatsapp_inbox#239.

    The turn ends `done`: nothing broke, so the failure guard of whatsapp_inbox#122 lets the run
    through. But the model may have ended it without a word — typically when it called its answer
    tool with no text beside the call (`crates/server/src/agent_runner.rs` publishes that turn's
    text, which is then `""`). The `notify` that quotes `{{steps.<ai>.text}}` then queues an EMPTY
    message to her phone (the kernel sends an empty string as written), or — when the key is not
    there at all — refuses and ends the run as `failed`. Either way the last thing she hears is
    «let me check, I will come straight back to you».

    The kernel's conditions are AND only, so «failed OR said nothing» is two guards, not one. For
    EVERY `ai` step a WhatsApp `notify` spoke before and whose `text` a WhatsApp `notify` quotes:

    * right after the `condition` that ends the run when the turn FAILED (#122) — so a failed turn
      is never apologised for twice — a WhatsApp `notify` to the acknowledged number, with FIXED
      words, guarded by `run_if: {"steps.<ai>.text": {"in": ["", null]}}` AND, for every `options`
      output the step declares, `{"steps.<ai>.<field>": {"eq": []}}`: no words and nothing to tap
      is silence; no words but slots to tap is an answer, and she gets the list, not an apology;
    * every WhatsApp `notify` that quotes the text is guarded by
      `run_if: {"steps.<ai>.text": {"exists": true, "neq": ""}}`: `neq ""` alone lets a missing
      key through (`null` is not `""`), and the kernel then refuses the message and ends the run.
    """
    steps = doc.get("steps", [])
    problems = []
    acknowledged = None
    for i, step in enumerate(steps):
        if step.get("kind") == "notify" and step.get("channel") == "whatsapp":
            if acknowledged is None:
                acknowledged = step
            continue
        if step.get("kind") != "ai" or acknowledged is None:
            continue
        sid = step.get("id")
        text_path = f"steps.{sid}.text"
        failed_stop = next(
            (
                j for j in range(i + 1, len(steps))
                if steps[j].get("kind") == "condition"
                and (steps[j].get("when") or {}).get(f"steps.{sid}.status") == {"neq": "failed"}
            ),
            None,
        )
        at = (failed_stop if failed_stop is not None else i + 2) + 1
        replies = [
            s for s in steps[i + 1:]
            if s.get("kind") == "notify"
            and s.get("channel") == "whatsapp"
            and "{{" + text_path + "}}" in json.dumps(s.get("vars") or {})
        ]
        if not replies:
            continue
        for reply in replies:
            if reply.get("run_if") != {text_path: {"exists": True, "neq": ""}}:
                problems.append(
                    f"{name} step `{reply.get('id')}` sends her the words of `{sid}` without "
                    f'`"run_if": {{"{text_path}": {{"exists": true, "neq": ""}}}}`: when the '
                    f"assistant said nothing, an EMPTY message reaches her phone — or, with no "
                    f"text at all, the kernel refuses it and the run dies unanswered"
                )
        guard = {text_path: {"in": ["", None]}}
        for field, spec in (step.get("output") or {}).items():
            if isinstance(spec, dict) and spec.get("type") == "options":
                guard[f"steps.{sid}.{field}"] = {"eq": []}
        silence = steps[at] if at < len(steps) else {}
        if not (
            silence.get("kind") == "notify"
            and silence.get("channel") == "whatsapp"
            and silence.get("run_if") == guard
        ):
            problems.append(
                f"{name} step `{sid}` is not followed, right after the condition that stops a "
                f"FAILED turn, by a WhatsApp `notify` guarded by `\"run_if\": "
                f"{json.dumps(guard)}`: when the assistant answers with no words and nothing to "
                f"tap, nothing tells her that the business will answer"
            )
            continue
        text = str((silence.get("vars") or {}).get("text") or "")
        if not text.strip() or "{{" in text:
            problems.append(
                f"{name} step `{silence.get('id')}` is the message she gets when `{sid}` said "
                f"nothing, and its words are not FIXED ({text!r}): the step that should have "
                f"written them wrote nothing"
            )
        if silence.get("to") != acknowledged.get("to"):
            problems.append(
                f"{name} step `{silence.get('id')}` does not write to the number the "
                f"acknowledgement `{acknowledged.get('id')}` went to: the apology reaches "
                f"somebody else, or nobody"
            )
    return problems


# The rules `main()` has to apply to EVERY real document. `self_check()` proves each of them against
# synthetic documents — which is exactly why deleting the one line that applied a rule to the REAL
# templates used to leave the battery green (whatsapp_inbox#69, mutant N5): the cases still passed,
# and nothing said the rule had never met a document. `main()` writes every application down in a
# ledger through `applied()` and fails on any (rule, document) pair that is missing.
def applied(ledger, rule, name, doc, *args):
    """Runs `rule` on one document and records it — the call and the record are ONE line."""
    ledger.add((rule.__name__, name))
    return rule(name, doc, *args)


def prompt_of(step):
    """The prompt text of an `ai` step, or `""` for every other kind."""
    return step.get("prompt") if step.get("kind") == "ai" and isinstance(step.get("prompt"), str) else ""


def undeclared_tool_problems(name, doc, known):
    """An operation the prompt TELLS the model to use, that the step never handed it.

    The failure mode of every branch added to a prompt, and it is silent in the worst way: the
    author writes «if they want to cancel, call `appointments.appointments.cancel`», forgets to add
    the name to `tools.commands`, and the model is ordered to use a tool it was never given. Nothing
    errors — there is nothing to error. It improvises: it apologises, it invents, or it reaches for
    the closest tool it DOES have, which in this template is the one that BOOKS. The customer who
    asked to cancel gets a second appointment, which is whatsapp_inbox#61 arriving through its own
    fix.

    Judged only against names some module in the workspace really declares (`known`), so the prose
    of a prompt stays prose: `internal_notes`, `duration_minutes` and `start_datetime` are fields,
    not operations, and nothing here should have to escape them.
    """
    problems = []
    for step in doc.get("steps", []):
        prompt = prompt_of(step)
        if not prompt:
            continue
        tools = step.get("tools") or {}
        handed = set((tools.get("queries") or []) + (tools.get("commands") or []))
        for op in sorted(known - handed):
            if f"`{op}`" in prompt:
                problems.append(
                    f"{name} step `{step.get('id')}` tells the model to use `{op}`, which is not in "
                    f"its `tools`. The model is not refused — it is handed a different set than the "
                    f"one its orders name, so it improvises with what it HAS. Declare it, or stop "
                    f"naming it"
                )
    return problems


def unordered_tool_problems(name, doc):
    """A tool the step HANDS the model that its prompt never tells it to use.

    The mirror image of `undeclared_tool_problems`, and the same hole seen from the other side:
    there the orders name a tool that was never handed over; here a tool is handed over that no
    order names. Measured on whatsapp_inbox#61 — delete the whole CANCELLING branch from the
    prompt, keep `appointments.appointments.cancel` in `tools.commands`, and the battery stayed
    green: the grants still matched the tools, the tools still existed, and the customer who wrote
    «cancel it» was back to getting a second appointment while the salon had granted the automation
    the power to cancel for nothing. A permission nobody is told to spend is a door left open — and
    a branch of the prompt that vanishes is only visible through the tool it leaves orphaned.

    Every handed tool has to be named in backticks somewhere in the prompt. Nothing more: this does
    not judge WHAT the prompt says about it, only that it says something.
    """
    problems = []
    for step in doc.get("steps", []):
        if step.get("kind") != "ai":
            continue
        prompt = prompt_of(step)
        tools = step.get("tools") or {}
        for op in (tools.get("queries") or []) + (tools.get("commands") or []):
            if f"`{op}`" not in prompt:
                problems.append(
                    f"{name} step `{step.get('id')}` hands the model `{op}` and its prompt never "
                    f"tells it to use it: a grant the owner was asked for that no order spends, "
                    f"or a branch of the prompt that went missing. Name it, or stop handing it over"
                )
    return problems


# `crates/runtime/src/flows/def.rs::MAX_ITERS_CAP` — the hub REFUSES a document whose `ai` step asks
# for more, so a template past it is one no hub can save. `flow.schema.json` says the same, but that
# layer needs a hub checkout (the monorepo sibling or the gate's `ERPLORA_HUB_DIR`): this one needs
# nothing, so the cap holds on a bare local checkout too.
MAX_ITERS_CAP = 10


def budget_problems(name, doc):
    """`max_iters` of every `ai` step within what the hub accepts (1..=MAX_ITERS_CAP).

    `propose_appointment` sits AT the cap on purpose (whatsapp_inbox#55): booking chains up to nine
    tool calls in one turn, so a branch added to that prompt has to be one that EXCLUDES the others
    (cancelling is: three calls, never alongside booking — whatsapp_inbox#61), never one that
    lengthens the chain. The only relief an author reaches for when the chain grows is this number,
    and the hub takes the whole document away when it goes past ten.
    """
    problems = []
    for step in doc.get("steps", []):
        if step.get("kind") != "ai" or "max_iters" not in step:
            continue
        n = step.get("max_iters")
        if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= MAX_ITERS_CAP:
            problems.append(
                f"{name} step `{step.get('id')}` asks for `max_iters` {n!r}: the hub accepts 1 to "
                f"{MAX_ITERS_CAP} (`def.rs::MAX_ITERS_CAP`) and refuses the whole document past "
                f"that — split the step, do not raise the number"
            )
    for step in doc.get("steps", []):
        if step.get("kind") != "ai":
            continue
        tools = step.get("tools") or {}
        handed = (tools.get("commands") or []) + (tools.get("queries") or [])
        if handed and step.get("max_iters") == 1:
            problems.append(
                f"{name} step `{step.get('id')}` is handed {len(handed)} tool(s) and one single "
                f"turn: `max_iters` counts MODEL CALLS (`agent_runner.rs`, `for _ in "
                f"0..max_iters`), so the call spends the only turn there was and the step dies "
                f"with `flow.agent_max_iters` — the customer is not answered at all, by anybody. "
                f"Two is the floor that works (ask, then answer) and a step that reads twice "
                f"before writing needs three"
            )
    return problems


# «`channel` set to `customer`», «`channel` puesto a `customer`», «`channel` = `customer`» — the three
# ways a prompt of this module ORDERS a value for a payload field. An order phrased any other way is
# prose this rule cannot read: it stays blind to it, never wrong about it.
ORDERED_VALUE = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)`\s+(?:set to|puesto a|=)\s+`([^`]+)`")


def payload_enums(commands_def):
    """`command id -> {property: [allowed values]}` for every enum property a command's payload
    schema declares. A command without a `schema`, or whose file is not there, declares none."""
    out = {}
    for cid, (module_dir, cdef) in commands_def.items():
        rel = cdef.get("schema")
        if not isinstance(rel, str) or module_dir is None:
            continue
        path = pathlib.Path(module_dir) / rel
        if not path.is_file():
            continue
        props = json.loads(path.read_text()).get("properties") or {}
        enums = {
            prop: list(spec["enum"])
            for prop, spec in props.items()
            if isinstance(spec, dict) and isinstance(spec.get("enum"), list)
        }
        if enums:
            out[cid] = enums
    return out


def enum_value_problems(name, doc, enums):
    """A value the prompt ORDERS for a payload field that the command's own schema refuses.

    whatsapp_inbox#61 as written said `channel: "whatsapp"`; `appointments.appointments.cancel` is
    `additionalProperties: false` with `channel` in `["staff", "customer"]`, and it is `customer`
    that makes `allow_customer_cancellation` and `cancellation_notice_hours` apply at all. The wrong
    word is not a wrong history line: the hub validates the payload again at approval
    (`decide_flow_approval` → `commands::validate_payload`), so the salon approves and the proposal
    stays PENDING with `invalid_payload` — the cancellation never runs and the customer is told
    nothing, which is whatsapp_inbox#70 reached through a typo.

    Judged only for fields whose schema declares an `enum`, and only against the commands the step
    hands over: `phone` = `+{{input.from}}` addresses a query and is nobody's enum.
    """
    problems = []
    for step in doc.get("steps", []):
        prompt = prompt_of(step)
        if not prompt:
            continue
        handed = ((step.get("tools") or {}).get("commands")) or []
        for prop, value in ORDERED_VALUE.findall(prompt):
            for cname in handed:
                allowed = (enums.get(cname) or {}).get(prop)
                if allowed is not None and value not in allowed:
                    problems.append(
                        f"{name} step `{step.get('id')}` tells the model to send `{prop}` = "
                        f"`{value}`, and `{cname}` only accepts {allowed}: the salon would approve "
                        f"a proposal the hub then refuses as `invalid_payload`, and the customer "
                        f"hears nothing"
                    )
    return problems


# `command -> {(field, value) a prompt may ORDER: the companion field that has to travel with it}`.
#
# A payload field that is mandatory only in COMBINATION with another one is invisible to every
# layer above. It is not in the schema's `required` — the rule reads two fields at once and is
# decided against the appointment row, so the handler owns it
# (`appointments/handler/src/lib.rs::cancel_appointment_pure`) — `additionalProperties` accepts a
# payload without it, and `enum_value_problems` only judges the VALUE of the field the prompt does
# order. So a template that orders `channel` = `customer` and never says WHO is asking parses,
# saves, arms its trigger, is approved by the salon, and is refused at the last step with
# `invalid_payload: customer_id is required when channel is `customer``: the customer who wrote
# «cancel it» is told nothing and keeps the chair (whatsapp_inbox#82, the door appointments#140
# closed on purpose so that an external channel wired without the customer fails LOUDLY).
IDENTITY_BOUND_PAYLOAD = {
    "appointments.appointments.cancel": {("channel", "customer"): "customer_id"},
    # Since appointments#144 (v1.1.73) moving carries the same pair as cancelling and shares the
    # same guard (`customer_identity_refusal`), so it earns the same row: an instruction that
    # orders the customer channel and forgets who the customer is fails as `invalid_payload`
    # AFTER the salon approved it, and the customer hears nothing (whatsapp_inbox#105).
    "appointments.appointments.reschedule": {("channel", "customer"): "customer_id"},
}


def identified_cancellation_problems(name, doc):
    """An INSTRUCTION that orders the customer channel and never orders WHO the customer is.

    Reached through `ORDERED_VALUE`, the same three phrasings `enum_value_problems` reads, so the
    two rules see the same orders: that one judges the value, this one judges what has to come WITH
    it. The companion only has to be NAMED in backticks — like `unordered_tool_problems`, this does
    not judge what the prompt SAYS about it, only that it says something, because the sentence is
    prose and prose is not this battery's business.

    🔴 Judged line by line, and that is the whole rule rather than a detail. Asking for the
    companion anywhere in the prompt was the first version, and its own mutant survived: these
    prompts explain underneath WHY the id travels with the channel, so stripping the field from the
    numbered instruction that orders the call left the explanation behind and the battery green
    over a template that no longer sends it. The order and its fields are one instruction; a
    paragraph about them further down is not the order.
    """
    problems = []
    for step in doc.get("steps", []):
        prompt = prompt_of(step)
        if not prompt:
            continue
        handed = ((step.get("tools") or {}).get("commands")) or []
        for line in prompt.split("\n"):
            ordered = set(ORDERED_VALUE.findall(line))
            if not ordered:
                continue
            for cname in handed:
                for (field, value), companion in sorted((IDENTITY_BOUND_PAYLOAD.get(cname) or {}).items()):
                    if (field, value) not in ordered or f"`{companion}`" in line:
                        continue
                    problems.append(
                        f"{name} step `{step.get('id')}` orders `{field}` = `{value}` for "
                        f"`{cname}` in an instruction that never names `{companion}`: that pair is "
                        f"what makes the command demand who is asking, so the call is refused as "
                        f"`invalid_payload` after the salon has already approved it, and the "
                        f"customer hears nothing"
                    )
    return problems


def payload_properties(commands_def):
    """`command id -> {property names}` for every command whose payload schema is readable.

    The anchor of `IDENTITY_BOUND_PAYLOAD`: a table of field names written HERE about a schema that
    lives in ANOTHER repository is a rule that can go quietly wrong in two directions, and this is
    the one that cannot be seen from this side — `appointments` renaming or dropping `customer_id`
    would leave this battery demanding a word no command accepts, green forever over a template
    that always fails.
    """
    out = {}
    for cid, (module_dir, cdef) in commands_def.items():
        rel = cdef.get("schema")
        if not isinstance(rel, str) or module_dir is None:
            continue
        path = pathlib.Path(module_dir) / rel
        if not path.is_file():
            continue
        out[cid] = set((json.loads(path.read_text()).get("properties") or {}).keys())
    return out


def identity_field_problems(name, doc, props, enums=None):
    """Every field the tables here name is one the command's own schema really declares.

    A document rule that never reads the document, and on purpose: what it needs is the ledger. As
    a one-off call in `main()` it was the only check here that nothing required — deleting its
    single line let `appointments` rename or drop `customer_id` with this battery green over
    templates that would then fail on every cancellation (measured: the mutant survived). Registered
    like every other rule, that deletion is refused by name.

    Two tables ride on the same anchor because they fail the same way and only from over here.
    `IDENTITY_BOUND_PAYLOAD` names a field the templates must SEND; `PINNED_COMMAND_PAYLOAD` names
    a field and a VALUE the grant FIXES, which is worse when it goes stale: a pin is applied before
    the schema (`check_command_grant`), so a pin naming a word `appointments` no longer accepts does
    not degrade — it refuses every cancellation this channel ever makes, with the templates, the
    grants and every other rule here green.
    """
    problems = []
    for cname, pairs in sorted(IDENTITY_BOUND_PAYLOAD.items()):
        declared = props.get(cname)
        if declared is None:
            continue  # no readable schema next door: layer 1b already said so out loud
        for (field, value), companion in sorted(pairs.items()):
            for prop in (field, companion):
                if prop not in declared:
                    problems.append(
                        f"{name}: IDENTITY_BOUND_PAYLOAD names `{prop}` for `{cname}`, whose "
                        f"schema declares {sorted(declared)}: the table is about a contract that "
                        f"lives in another repository and that contract moved, so this rule is now "
                        f"asking the templates for a word nothing accepts"
                    )
    for cname, fixed in sorted(PINNED_COMMAND_PAYLOAD.items()):
        declared = props.get(cname)
        if declared is None:
            continue
        for field, value in sorted(fixed.items()):
            if field not in declared:
                problems.append(
                    f"{name}: PINNED_COMMAND_PAYLOAD fixes `{field}` for `{cname}`, whose schema "
                    f"declares {sorted(declared)}: the grant would pin a field the command does "
                    f"not take, and the hub applies a pin BEFORE the schema — every call this "
                    f"channel makes is refused as `flow.grant_payload_denied`"
                )
                continue
            allowed = (enums or {}).get(cname, {}).get(field)
            if allowed is not None and value not in allowed:
                problems.append(
                    f"{name}: PINNED_COMMAND_PAYLOAD fixes `{field}` = `{value}` for `{cname}`, "
                    f"which only accepts {allowed}: the grant pins a value the command refuses, so "
                    f"the pin stops being «narrower» and becomes «never»"
                )
    return problems


def sent_payload_fields():
    """`command id -> {field names}` this repo puts in a payload, from BOTH tables that name one.

    `IDENTITY_BOUND_PAYLOAD` names what the prompts must SEND and `PINNED_COMMAND_PAYLOAD` what the
    grant FIXES; against a neighbour one release too old they fail the same way, so the floor reads
    them as one list.
    """
    out = {}
    for cname, pairs in IDENTITY_BOUND_PAYLOAD.items():
        for (field, _value), companion in pairs.items():
            out.setdefault(cname, set()).update((field, companion))
    for cname, fixed in PINNED_COMMAND_PAYLOAD.items():
        out.setdefault(cname, set()).update(fixed)
    return out


def git_in(module_dir, *args):
    """`git -C <module_dir> …` — `(stdout, None)` or `(None, reason)`, never a raised exception.

    A neighbour that is not a checkout, or a `git` that is not installed, has to come back as a
    REASON this battery prints and skips over: raising here would turn «I could not look at the
    past» into a red that reads exactly like «the floor is wrong», which are opposite answers.
    """
    try:
        done = subprocess.run(
            ("git", "-C", str(module_dir)) + args,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"`git` could not be run ({e})"
    if done.returncode != 0:
        return None, (done.stderr.strip().splitlines() or ["git failed"])[0]
    return done.stdout, None


def release_commit(module_dir, version):
    """The commit whose tree the marketplace published AS `version` — `(sha, None)` or `(None, why)`.

    Read out of the neighbour's own git history, because that is the only copy of the past there
    is: the module repos carry no tags at all (`git tag` is empty in every one of them), so a
    release is found as the commit whose `module.json` declares exactly that version.

    🔴 **The FIRST commit to declare it, not the last.** A version's zip is uploaded CREATE-ONLY
    (`modules/{id}/v{version}.zip`), so the tree that becomes `vX` is the one pushed when `vX` was
    first declared — the `chore(release): vX` commit — and everything merged AFTERWARDS while the
    manifest still reads `vX` never reaches that zip at all. Measured on `appointments` while
    closing whatsapp_inbox#125: `f213ade` is `chore(release): v1.1.25` and does NOT declare
    `appointments.appointment.confirmed`; `39942c2` (appointments#40) adds the declaration with the
    manifest still reading 1.1.25, so it shipped in **1.1.26** (`f3426cd`) and never in 1.1.25.
    Reading the newest commit at a version would answer «1.1.25 declares it» about a zip that does
    not, which is the exact reading this whole layer exists to distrust.

    ⚠️ `-S` answers with the commits where the count of the string CHANGED, which is the one that
    added the version and the one that bumped it away — and the newest is usually the second. So
    every candidate is opened and only the one whose manifest really reads that version answers.
    Taking the first sha reads the release ABOVE the floor (measured by hand: `-S '"version":
    "1.1.72"' -n1` on `appointments/` answers `7c1c7f9`, which IS 1.1.73).
    """
    out, why = git_in(module_dir, "rev-parse", "--git-dir")
    if out is None:
        return None, f"{module_dir.name}/ is not a git checkout ({why})"
    out, why = git_in(
        module_dir, "log", "--format=%H", "-S", f'"version": "{version}"', "--", "module.json"
    )
    if out is None:
        return None, f"the history of {module_dir.name}/module.json could not be read ({why})"
    for sha in out.split():
        blob, _ = git_in(module_dir, "show", f"{sha}:module.json")
        if blob is None:
            continue
        try:
            if (json.loads(blob) or {}).get("version") != version:
                continue
        except ValueError:
            continue
        return sha, None
    return None, f"no commit of {module_dir.name}/ declares version {version}"


def schema_at_version(module_dir, version, rel):
    """The `properties` a command's payload schema declared AT a released version of its module.

    Read out of the neighbour's own git history, because that is the only copy of the past there
    is: the module repos carry no tags at all (`git tag` is empty in every one of them), so a
    release is found as the commit whose `module.json` declares exactly that version.

    ⚠️ `-S` answers with the commits where the count of the string CHANGED, which is the one that
    added the version and the one that bumped it away — and the newest is usually the second. So
    every candidate is opened and only the one whose manifest really reads that version answers.
    Taking the first sha reads the schema of the release ABOVE the floor, which is precisely the
    reading this rule exists to distrust (measured by hand: `-S '"version": "1.1.72"' -n1` on
    `appointments/` answers `7c1c7f9`, which IS 1.1.73).

    Returns `(properties, None)` or `(None, reason)` — never a quiet empty set, because «the field
    was not there» and «I could not look» are opposite answers and only one of them is a bug.
    """
    sha, why = release_commit(module_dir, version)
    if sha is None:
        return None, why
    blob, why = git_in(module_dir, "show", f"{sha}:{rel}")
    if blob is None:
        return None, f"{module_dir.name}/{rel} is not in the tree of {version} ({why})"
    try:
        return set((json.loads(blob).get("properties") or {}).keys()), None
    except ValueError as e:
        return None, f"{module_dir.name}/{rel} at {version} is not readable JSON ({e})"


def emits_at_version(module_dir, version):
    """The events a neighbour DECLARED it emits in the tree published as `version`.

    The twin of {@link schema_at_version} for the other half of a template: not what it SENDS but
    what it WAKES UP for. Read from the same released tree and for the same reason — the floor
    travels to the hub (hub#1611) and decides whether the recipe is OFFERED, so what matters is
    what that published zip declared, never what the checkout on this machine declares today.

    ⚠️ A module that declares NO events answers with an empty set, not with a reason: «it emitted
    nothing» is an answer, and the rule that reads this has to be able to fail on it. Only «I could
    not look» comes back as a reason, because a floor nobody could read and a floor that is high
    enough look identical from here.
    """
    sha, why = release_commit(module_dir, version)
    if sha is None:
        return None, why
    blob, why = git_in(module_dir, "show", f"{sha}:module.json")
    if blob is None:
        return None, f"{module_dir.name}/module.json is not in the tree of {version} ({why})"
    try:
        emits = ((json.loads(blob) or {}).get("events") or {}).get("emits")
    except ValueError as e:
        return None, f"{module_dir.name}/module.json at {version} is not readable JSON ({e})"
    return {e for e in emits if isinstance(e, str)} if isinstance(emits, list) else set(), None


# `sql_names_at_version`'s answer when the query does not exist in the release published as the
# floor — an ANSWER, the opposite of «could not look» (whatsapp_inbox#173).
ABSENT_AT_FLOOR = object()

SQL_COMMENT = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)
SQL_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def sql_names_at_version(module_dir, version, qid):
    """Every identifier query `qid`'s SQL MENTIONS in the tree published as `version`, comments out.

    «Mentions», not «selects», on purpose: telling an output column from a filter would need a SQL
    parser, and the names a template reads are output aliases (`… AS start_date_label`) that only
    ever appear in the release that answers them. The price is a false GREEN when a template reads
    a name the query only filters by — never a false red. Comments are stripped because a release
    note can name a column before the SELECT does.

    The query is looked up in the manifest OF THAT RELEASE, not in today's: what the hub installs at
    the floor is that zip, and its `sql` path is the one that answers.

    Returns `(names, None)`, `(ABSENT_AT_FLOOR, None)` or `(None, reason)`. 🔴 «The release does not
    declare the query, or declares it over a file its tree does not carry» is an ANSWER — the read
    does not exist at the floor, so the step fails on every run — and only «I could not look» (no
    checkout, no such release, a manifest that is not JSON) is a reason. Until whatsapp_inbox#173
    both came back as a reason and a floor BELOW the query was printed as a skip, green.
    """
    sha, why = release_commit(module_dir, version)
    if sha is None:
        return None, why
    blob, why = git_in(module_dir, "show", f"{sha}:module.json")
    if blob is None:
        return None, f"{module_dir.name}/module.json could not be read at {version} ({why})"
    try:
        qdef = ((json.loads(blob) or {}).get("queries") or {}).get(qid)
    except ValueError as e:
        return None, f"{module_dir.name}/module.json at {version} is not readable JSON ({e})"
    if not isinstance(qdef, dict):
        return ABSENT_AT_FLOOR, None
    rel = qdef.get("sql")
    if not isinstance(rel, str):
        return None, f"`{qid}` declares no `sql` file at {version}, so what it answered could not be read"
    blob, _ = git_in(module_dir, "show", f"{sha}:{rel}")
    if blob is None:
        return ABSENT_AT_FLOOR, None
    return set(SQL_NAME.findall(SQL_COMMENT.sub(" ", blob))), None


def floor_read_columns(floors, definitions, resolved, qids):
    """`query id -> {names its SQL mentions}` AS OF the floor, for the `qids` a family reads —
    or `ABSENT_AT_FLOOR` when that release has no such query (whatsapp_inbox#173).

    Returns the map and the floors it could not read, printed as skips by `main()` — an unreadable
    floor and a floor that is high enough look identical from here.
    """
    out, skipped = {}, []
    for qid in sorted(qids):
        module_id = qid.split(".", 1)[0]
        floor = floors.get(module_id)
        target = definitions.get(qid)
        if floor is None or target is None or module_id not in resolved:
            continue  # unfloored, or already reported as a name no module declares
        module_dir, _ = target
        names, why = sql_names_at_version(module_dir, floor, qid)
        if names is None:
            skipped.append(
                f"what `{qid}` answered as of the declared floor {floor} could not be read "
                f"({why}) — the columns these templates read from it were NOT verified"
            )
            continue
        out[qid] = names
    return out, skipped


def floor_payload_properties(floors, commands_def, resolved):
    """`command id -> {declared property names}` AS OF the floor this family declares.

    The twin of `payload_properties`, one or more releases behind on purpose. That one reads the
    neighbour's WORKING TREE — whatever checkout this machine happens to hold, which on a developer
    box is the newest thing there is; this one reads the OLDEST version these templates promise to
    work on. They answer different questions, and only both together say «what this recipe sends is
    taken everywhere this recipe is offered».

    Returns `(props, skipped)`: a command whose past could not be read is named out loud, never
    dropped, because an unreadable floor and a floor that is high enough look identical from here.
    """
    props, skipped = {}, []
    owners = {module_dir: mid for mid, (module_dir, _) in resolved.items()}
    for cname in sorted(sent_payload_fields()):
        target = commands_def.get(cname)
        if target is None:
            continue  # a name no module declares — layer 3 already says so
        module_dir, cdef = target
        floor = floors.get(owners.get(module_dir))
        if floor is None:
            continue  # this family pins no floor for that module: nothing to read against
        rel = cdef.get("schema")
        if not isinstance(rel, str):
            continue  # a command with no payload schema declares no field to be missing
        declared, why = schema_at_version(module_dir, floor, rel)
        if declared is None:
            skipped.append(
                f"the payload of `{cname}` as of the declared floor {floor} could not be read "
                f"({why}) — whether that floor is high enough for what these templates SEND was "
                f"NOT verified"
            )
            continue
        props[cname] = declared
    return props, skipped


def floor_field_problems(name, doc, floor_props):
    """Every field these templates SEND is one the command ALREADY TOOK at the declared floor.

    The floor stopped being a footnote of this battery with hub#1611: `requires.json` TRAVELS to
    the hub, and `flow_template_floor_is_met` (`crates/runtime/src/registry.rs`) is what decides
    whether a recipe is OFFERED at all. So the floor is the oldest neighbour this template promises
    to work on, and a floor one release too low is a promise the command refuses to keep.

    🔴 Measured, and it is the whole reason this rule exists (whatsapp_inbox#105, mutant M9).
    `channel` + `customer_id` enter `appointments.appointments.reschedule` in 1.1.73. Leaving the
    floor at 1.1.72 left every other rule here green: layer 1b only compares the floor against the
    checkout on THIS machine, which is newer, so it printed `RESOLVED appointments@1.1.73 (needs
    >= 1.1.72)` and said nothing, and `identity_field_problems` reads that same new working tree.
    A hub sitting at exactly 1.1.72 would then be offered the recipe against a schema that is
    `additionalProperties: false` without those fields: every customer who asks to move her
    appointment is told it is being moved and the call comes back `invalid_payload`.
    """
    problems, sent = [], sent_payload_fields()
    for step in doc.get("steps", []):
        for cname in ((step.get("tools") or {}).get("commands")) or []:
            declared = floor_props.get(cname)
            if declared is None:
                continue  # unfloored or unreadable: `main()` said so out loud
            for field in sorted((sent.get(cname) or set()) - declared):
                problems.append(
                    f"{name} step `{step.get('id')}` hands over `{cname}`, whose payload this repo "
                    f"fills with `{field}`, and at the floor this family declares that command "
                    f"took {sorted(declared)}: the floor is below the release that started taking "
                    f"the field, so the hub OFFERS this recipe to a copy that answers "
                    f"`invalid_payload` to every one of these calls — raise `modules` in "
                    f"`{name.split('.')[0]}.requires.json` to the version that introduced it"
                )
    return problems


def floor_emitted_events(floors, resolved):
    """`module id -> {events it DECLARED it emits}` AS OF the floor this family declares.

    The twin of {@link floor_payload_properties} for the WAKE-UP half. Returns the map and the
    floors it could not read, so `main()` can print them as skips: an unreadable floor and a floor
    that is high enough look identical from here, and only one of them is a bug.
    """
    out, skipped = {}, []
    for module_id, floor in sorted(floors.items()):
        target = resolved.get(module_id)
        if target is None:
            continue  # not in the workspace: `main()` already says that module was not verified
        module_dir, _ = target
        emits, why = emits_at_version(module_dir, floor)
        if emits is None:
            skipped.append(
                f"what `{module_id}` declared it emits as of the declared floor {floor} could not "
                f"be read ({why}) — whether that floor is high enough for the event these "
                f"templates WAIT ON was NOT verified"
            )
            continue
        out[module_id] = emits
    return out, skipped


def floor_trigger_problems(name, doc, floor_emits):
    """The event a family waits on was ALREADY DECLARED by its neighbour at the declared floor.

    The mirror of {@link floor_field_problems}: that rule holds the floor to what these templates
    SEND, this one to what wakes them up. Both exist because the floor TRAVELS to the hub since
    hub#1611 and `flow_template_floor_is_met` decides with it whether a recipe is OFFERED at all —
    so a floor below the release that started declaring the event hands the recipe to a hub where
    the trigger matches nothing and the automation never runs once.

    🔴 And it fails the SAME WAY the bug it was born from does, which is why it is worth a rule
    instead of a careful reading. `appointments.appointment.confirmed` has been emitted by
    `appointments.appointments.confirm` since the module's first commit, but the module did not
    DECLARE it in `events.emits` until appointments#40 — and what a neighbour may consume is what
    is declared, not what happens by ricochet. A recipe offered to a hub below that release is a
    salon pressing «Confirmar» and no message leaving: exactly the silence of whatsapp_inbox#125,
    now with a settings card reading «Activo» over it. Nothing else here catches it — every other
    layer resolves the neighbour against the CHECKOUT on this machine, which is newer, so this
    battery printed `RESOLVED appointments@1.1.73 (needs >= 1.1.25)` and went green over a floor
    one release too low.

    Silent by design on: a trigger that is not an event, an event whose owner this family pins no
    floor for (`hub.*` is the core, not a neighbour), and a floor `main()` could not read.
    """
    problems = []
    for trigger in doc.get("triggers") or []:
        if not isinstance(trigger, dict) or trigger.get("kind") != "event":
            continue
        event = trigger.get("event")
        if not isinstance(event, str) or "." not in event:
            continue  # shapeless: `family_trigger_problems` is the rule that judges that
        declared = floor_emits.get(event.split(".", 1)[0])
        if declared is None:
            continue  # unfloored or unreadable: `main()` said so out loud
        if event not in declared:
            problems.append(
                f"{name} wakes up on `{event}`, and at the floor this family declares its owner "
                f"declared it emits {sorted(declared) or 'nothing at all'}: the floor is below the "
                f"release that started DECLARING that event, so the hub OFFERS this recipe to a "
                f"copy where the trigger matches nothing and it never runs once — raise `modules` "
                f"in `{name.split('.')[0]}.requires.json` to the version that declared it"
            )
    return problems


# The keys a `kind: query` step answers with whatever the SQL says (`flows/query.rs`): written by
# the kernel, never a column, so no floor owes them.
QUERY_CONTRACT_KEYS = {"found", "count", "options"}
STEP_FIELD = re.compile(r"steps\.([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)")


def step_field_references(doc):
    """Every `steps.<id>.<field>` the document names — in a value, in a `{{…}}` text or as a KEY.

    Keys count because a `condition` spells its operands as keys (`"steps.x.phone": {"neq": ""}`),
    and a guard over a column the floor lacks is a guard over `null`.
    """
    refs = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(k)
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str):
            refs.update(STEP_FIELD.findall(node))

    walk(doc.get("steps") or [])
    return refs


def floor_read_column_problems(name, doc, floor_columns):
    """The columns a family READS off a neighbour's query were already there at the declared floor.

    The third twin of {@link floor_field_problems} (what the templates SEND) and
    {@link floor_trigger_problems} (what wakes them up): this one holds the floor to what they
    READ back. whatsapp_inbox#146 is why it exists — the confirmation now names the day and the
    hour through `start_date_label` / `start_time_label`, two columns `appointments.appointments.get`
    only answers since appointments#151 (1.1.77). The floor travels to the hub (hub#1611) and
    decides whether the recipe is OFFERED, so a floor below that release hands the recipe to a copy
    whose read has no such column: `{{steps.read_appointment.start_date_label}}` resolves to
    nothing and the customer receives the placeholder, which is worse than not saying the hour.

    `floor_columns` is `query id -> {names its SQL mentions at the floor}` (see
    {@link sql_names_at_version} for why «mentions» and not «selects»). Silent by design on a query
    whose owner this family pins no floor for and on a floor `main()` could not read.
    """
    readers = {
        s.get("id"): s.get("query")
        for s in doc.get("steps") or []
        if isinstance(s, dict) and s.get("kind") == "query"
    }
    problems = []
    for step_id, qid in sorted(readers.items(), key=lambda kv: str(kv[0])):
        if floor_columns.get(qid) is ABSENT_AT_FLOOR:
            problems.append(
                f"{name} step `{step_id}` reads `{qid}`, and the release this family declares as "
                f"its floor does not have that query: the hub OFFERS this recipe to a copy where "
                f"the step fails on every run and nobody is answered — raise `modules` in "
                f"`{name.split('.')[0]}.requires.json` to the release that ships `{qid}`"
            )
    for step_id, field in sorted(step_field_references(doc)):
        qid = readers.get(step_id)
        columns = floor_columns.get(qid)
        if columns is None or columns is ABSENT_AT_FLOOR:
            continue  # unfloored, unreadable, or already reported above as a missing query
        if field in QUERY_CONTRACT_KEYS or field in columns:
            continue
        problems.append(
            f"{name} reads `steps.{step_id}.{field}` off `{qid}`, and the SQL of that query at "
            f"the floor this family declares has no `{field}`: the hub OFFERS this recipe to a "
            f"copy where the value resolves to nothing — a guard over `null`, or a customer "
            f"receiving an empty gap where the data should be — raise `modules` in "
            f"`{name.split('.')[0]}.requires.json` to the release that started answering it"
        )
    return problems


def neighbour_operations(step):
    """The operation names ONE step makes the hub run: its `query`, its `command`, and every tool
    an `ai` step is handed (`tools.queries` + `tools.commands`), in document order."""
    kind = step.get("kind")
    if kind == "query":
        names = [step.get("query")]
    elif kind == "command":
        names = [step.get("command")]
    elif kind == "ai":
        tools = step.get("tools") or {}
        names = list(tools.get("queries") or []) + list(tools.get("commands") or [])
    else:
        names = []
    return [n for n in names if isinstance(n, str) and "." in n]


def unfloored_read_problems(name, doc, floors):
    """Every NEIGHBOUR a family runs an operation of has a floor in its `requires.json`.

    The floor rules above only ever read what the family declares, so deleting a neighbour from
    `requires.json` did not make them fail — it made them silent: nothing to read against, nothing
    to report (whatsapp_inbox#173, measured by deleting `customers` from the reservation family).
    And the floor is not a note for this battery: it travels to the hub (hub#1611), where
    `flow_template_floor_is_met` decides with it whether the recipe is OFFERED — a neighbour with no
    floor is a recipe offered next to ANY copy of it, including one where the read does not exist.

    🔴 whatsapp_inbox#197: this rule first read only `query` steps, and the booking recipe hands its
    assistant `services.services.list`, `staff.members.list` and `staff.schedules.list_for_member`
    as TOOLS — so the recipe was offered next to any Services or Staff, and on one without those
    reads the assistant fails at the first question and the customer is left without her
    appointment. A tool is an operation the hub runs for the recipe exactly like a step is, so the
    `ai` step's `tools.queries`/`tools.commands` and every `command` step owe the same floor.

    `floors` is the `modules` map of the family's `requires.json`. This module's own operations owe
    no floor: they ship in the same zip as the recipe. One problem per neighbour per step.
    """
    own = MANIFEST.get("id")
    problems = []
    for step in doc.get("steps") or []:
        if not isinstance(step, dict):
            continue
        reported = set()
        for op in neighbour_operations(step):
            owner = op.split(".", 1)[0]
            if owner == own or owner in floors or owner in reported:
                continue
            reported.add(owner)
            problems.append(
                f"{name} step `{step.get('id')}` runs `{op}`, and `{name.split('.')[0]}.requires.json` "
                f"declares no floor for `{owner}`: the hub offers this recipe next to ANY copy of it, "
                f"including one without that operation — add `{owner}` to its `modules`"
            )
    return problems


def unattended_problems(name, doc):
    """A family that CALLS itself unattended has to actually run with nobody watching.

    whatsapp_inbox#58. The salon that asked for this has nobody sitting at the hub: the customer
    writes at 3 AM and the appointment has to exist at 3 AM. `-unattended` in the file name is what
    buys that family the exception `policy_problems` grants it — so it is also what this rule holds
    it to, because the failure it guards against is invisible from the outside. A document named
    `…-unattended` whose booking step is back on `policy: "manual"` still parses, still saves, still
    arms its trigger and still answers the customer with «we will confirm shortly». Nothing is
    refused. It simply parks the write in `_flow_approvals` and waits for a person who, in this
    business, does not exist — and the only symptom is an appointment that never appears.

    Two shapes are the same lie and both are checked:

    * an `ai` step that can PROPOSE a write and is not `auto` — the write parks;
    * an `approval` step anywhere — the kernel's explicit pause (hub#950). It stops the run dead
      on purpose, which is a legitimate thing for the attended sibling to do and a contradiction
      here.

    Silent on every other family: an attended template parking at a person is what it is FOR.
    """
    if not is_unattended(name):
        return []
    problems = []
    steps = doc.get("steps", [])
    for i in writing_ai_steps(doc):
        step = steps[i]
        if (step.get("policy") or "manual") != "auto":
            problems.append(
                f"{name} step `{step.get('id')}` can write and is `policy: "
                f"{step.get('policy') or 'manual'}`, in a family whose name promises that nobody "
                f"has to be watching. `manual` parks the write in `_flow_approvals` and ends the "
                f"turn, so the appointment waits for a person this business does not have — and "
                f"nothing anywhere says so: the document saves, the trigger arms and the customer "
                f"is answered"
            )
    for step in steps:
        if step.get("kind") == "approval":
            problems.append(
                f"{name} step `{step.get('id')}` is an `approval`: the kernel's explicit pause "
                f"(hub#950) stops the run until a person answers, which is the one thing this "
                f"family exists not to do. That step belongs in the attended sibling"
            )
    return problems


# The sentence that makes the unattended family habitable, in each language it ships in. It is
# prose, and this battery otherwise keeps out of prose on purpose (`undeclared_tool_problems`) —
# but this rule has no structural home: the kernel cannot tell «the start the customer asked for»
# from «a start the model picked», the document has no field for it, and a person is precisely
# what this family does without. The prompt is the only place the rule lives, so the prompt is
# what is pinned. Changing the wording means changing it here too, in the same commit: that is the
# point, not a nuisance — the wording IS the contract (whatsapp_inbox#58, reviewer mutant N2).
HOUR_RULE = {
    "en": "You never choose the hour. They do.",
    "es": "La hora no la eliges tú. La elige ella.",
}
BOOKING_COMMAND = "appointments.appointments.create"
CANCEL_COMMAND = "appointments.appointments.cancel"

# The same bet, one module over — whatsapp_inbox#60. A restaurant's unattended automation writes
# into `reservations` instead of `appointments`, and the harm is the same shape with one more
# field: an hour nobody asked for, or a party size nobody said, seats four people at a table for
# two. The wording is its own because the promise is its own — the chair sentence never mentions
# how many are coming.
TABLE_BOOKING_COMMAND = "reservations.reservations.create"
TABLE_RULE = {
    "en": "You never choose the hour or how many people are coming. They do.",
    "es": "Ni la hora ni cuántos sois lo eliges tú. Lo elige quien escribe.",
}

# `booking command -> the sentence its unattended family has to carry, per language`. A table
# rather than one constant because the rule travels with the WRITE, not with the module: any
# future family that books something unattended earns its row here, and a family whose booking
# command has no row is one this battery cannot vouch for.
BOOKING_RULES = {
    BOOKING_COMMAND: HOUR_RULE,
    TABLE_BOOKING_COMMAND: TABLE_RULE,
}


# ── «say what really happened, not what usually happens» — whatsapp_inbox#124 ─────────────────
#
# A booking made from this channel is NOT always confirmed, and the recipe used to write as if it
# were: «by the time they read this, it happened». Both modules decide the birth status from the
# business's own setting, and both ship it OFF-able:
#
# * `appointments` — `born_confirmed` in its handler is `auto_confirm_online` AND the booking
#   declaring itself made by the customer (`booked_online`). With the switch off, the appointment
#   is born `pending` and waits for somebody at the salon to accept it.
# * `reservations` — `_create_gated_insert.sql` writes `pending` unless `auto_confirm` is 1, and
#   its column DEFAULTS to 0, so the ordinary restaurant is the one that reviews.
#
# So the wording is not decoration: told «booked» over an appointment that is really waiting, the
# customer turns up to a slot the salon never accepted. Told «I have written you down, they will
# confirm» over one that is already in the diary, she waits for a message nobody is going to send
# and rings up to ask.
#
# `booking command -> the READ that says which of the two it will be`. It is a deterministic
# `query` step of the document and not a tool in the model's hands on purpose: `book_appointment`
# already sits AT `MAX_ITERS_CAP`, so one more read it has to remember to make is a read it
# sometimes will not make — and the branch it feeds is the sentence the customer reads.
BIRTH_STATUS_SOURCE = {
    BOOKING_COMMAND: "appointments.settings.get",
    TABLE_BOOKING_COMMAND: "reservations.settings.get",
}

# `booking command -> {language -> {status it is born with: the sentence that tells the truth}}`.
#
# Pinned as prose for the same reason `BOOKING_RULES` is (and `TAP_WORDS`, and `HOUR_RULE`): the
# branch has no structural home. The document cannot express «say this when the row comes back
# pending» — the kernel has no conditional inside an `ai` turn — and the command answers `{ok,
# operations, new_ids}` with no status in it, so the model cannot read the outcome afterwards
# either. What it CAN do is read the setting that decides it before it writes, which is what
# `BIRTH_STATUS_SOURCE` is for; the two sentences below are the two ends that reading leads to.
# Reword either of them and change it here in the same commit — the wording IS the promise.
BIRTH_STATUS_RULES = {
    BOOKING_COMMAND: {
        "en": {
            "confirmed": "When it is born confirmed, tell her it is booked.",
            "pending": (
                "When it is born pending, tell her you have written her in and the salon will "
                "confirm it here shortly."
            ),
        },
        "es": {
            "confirmed": "Si nace confirmada, dile que está reservada.",
            "pending": (
                "Si nace pendiente, dile que se la has apuntado y que el salón se la "
                "confirma por aquí en un momento."
            ),
        },
    },
    TABLE_BOOKING_COMMAND: {
        "en": {
            "confirmed": "When it is born confirmed, tell them the table is booked.",
            "pending": (
                "When it is born pending, tell them you have written it down and the restaurant "
                "will confirm it here shortly."
            ),
        },
        "es": {
            "confirmed": "Si nace confirmada, diles que la mesa está reservada.",
            "pending": (
                "Si nace pendiente, diles que la has apuntado y que el restaurante se la "
                "confirma por aquí en un momento."
            ),
        },
    },
}


def deterministic_reads(doc):
    """Every query a `kind: query` step of this document reads — the ones that always happen."""
    return {
        step.get("query")
        for step in doc.get("steps", [])
        if step.get("kind") == "query" and isinstance(step.get("query"), str)
    }


def birth_status_problems(name, doc):
    """The step that books tells the customer what really happened, both ways round.

    whatsapp_inbox#124. Two halves, and neither stands without the other:

    1. **The document READS the setting** that decides the birth status, deterministically, before
       the model is asked for anything. Without it the model is guessing, and the sentence it picks
       is the one the customer believes.
    2. **The prompt carries BOTH sentences**, in the language the document is written in — the one
       for a booking born `pending` and the one for a booking born `confirmed`. One of the two on
       its own is the bug this issue is about wearing the other face: the recipe that only knows
       «booked» lies to the salon that reviews, and a recipe that only knows «they will confirm»
       lies to the salon that does not.

    Judged per language for the reason `hour_choice_problems` is: the model reads the prompt in the
    language it is written in, so a Spanish document carrying the English sentence has the rule for
    nobody.
    """
    parts = name.split(".")
    lang = parts[1] if len(parts) >= 3 else ""
    reads = deterministic_reads(doc)
    problems = []
    for step in doc.get("steps", []):
        if step.get("kind") != "ai":
            continue
        commands = (step.get("tools") or {}).get("commands") or []
        prompt = prompt_of(step)
        for booking in sorted(BIRTH_STATUS_RULES):
            if booking not in commands:
                continue
            source = BIRTH_STATUS_SOURCE[booking]
            if source not in reads:
                problems.append(
                    f"{name} step `{step.get('id')}` can book with `{booking}` and no `kind: "
                    f"query` step of this document reads `{source}`: that read is the only thing "
                    f"in the run that knows whether the booking will be born `pending` or "
                    f"`confirmed`, and the command answers `{{ok, operations, new_ids}}` with no "
                    f"status in it. Without it the words sent to the customer are a guess"
                )
            wording = BIRTH_STATUS_RULES[booking].get(lang)
            if wording is None:
                problems.append(
                    f"{name} step `{step.get('id')}` can book with `{booking}` and this battery "
                    f"has no wording of the birth status for language `{lang}`: add the "
                    f"translation to `BIRTH_STATUS_RULES` in the same commit, or the promise is "
                    f"made to nobody who reads this document"
                )
                continue
            for status, sentence in sorted(wording.items()):
                if sentence in prompt:
                    continue
                problems.append(
                    f"{name} step `{step.get('id')}` can book with `{booking}` and its prompt no "
                    f"longer says what to write when the booking is born `{status}` "
                    f"(«{sentence}»). With one branch missing the recipe tells every customer the "
                    f"same thing, and it is wrong for half the businesses: «booked» over a "
                    f"booking that is still waiting sends her to a slot nobody accepted, and "
                    f"«they will confirm» over one already in the diary leaves her waiting for a "
                    f"message that is never coming"
                )
    return problems


# ── «read the switch in the shape it really comes back» — whatsapp_inbox#152 ───────────────────
#
# `booking_policy` hands the model the setting that decides the birth status, and the prompt has
# to say what its VALUES mean. That sentence is only true for the shape the read answers in, and
# the shape is the neighbour's, not ours: `reservations` answered its `auto_confirm` as the raw
# INTEGER column (`0`/`1`) until reservations#54 projected it as `auto_confirm <> 0`, which the
# runtime serialises as JSON `true`/`false`. A prompt still explaining `1`/`0` over a read that
# answers `true`/`false` gives the model a key that opens nothing — and the branch it then guesses
# is the sentence the customer believes. `BIRTH_STATUS_RULES` pins the two endings; this pins the
# sentence that picks between them, and the floor that makes it true.
#
# `booking command -> {language -> the sentence that says what each value of the switch means}`.
BIRTH_STATUS_READING = {
    BOOKING_COMMAND: {
        "en": (
            "`true` means the appointment you just made is already accepted, `false` means it is "
            "waiting for somebody at the salon to accept it."
        ),
        "es": (
            "`true` significa que la cita que acabas de hacer ya está aceptada, `false` que está "
            "esperando a que alguien del salón la acepte."
        ),
    },
    TABLE_BOOKING_COMMAND: {
        "en": (
            "`true` means the table you just booked is already accepted, `false` means it is "
            "waiting for somebody at the restaurant to accept it."
        ),
        "es": (
            "`true` significa que la mesa que acabas de reservar ya está aceptada, `false` que "
            "está esperando a que alguien del restaurante la acepte."
        ),
    },
}

# `booking command -> {language -> how to read an EMPTY answer}`. Not the same value in the two
# modules (see `flows/README.md`, «La receta dice la VERDAD»): a salon with no settings row
# confirms, a restaurant with none reviews. Said in the same `true`/`false` as the reading above.
BIRTH_STATUS_EMPTY = {
    BOOKING_COMMAND: {"en": "so read it as `true`.", "es": "así que léelo como `true`."},
    TABLE_BOOKING_COMMAND: {"en": "so read it as `false`.", "es": "así que léelo como `false`."},
}

# The integer wording the prompts used before reservations#54. Present next to the boolean one it
# is a prompt that contradicts itself, and the model is free to pick the stale half.
RAW_FLAG_WORDING = re.compile(
    r"`[01]` (?:means|significa)|, `[01]` (?:que|means)|read it as `[01]`|léelo como `[01]`"
    r"|comes back raw|viene crudo"
)

# `booking command -> (module, first release whose read answers the switch as a boolean, field)`.
# Below that floor the sentences above are false, so a family that books with the command has to
# declare at least this version in its `requires.json` — the hub reads that floor to decide whether
# the recipe is OFFERED (hub#1611). 3.0.30 is `chore(release): v3.0.30`, the first release after
# fc41c37 (reservations#58); `boolean_since_problems` re-reads it out of the neighbour's history.
BIRTH_STATUS_BOOLEAN_SINCE = {
    TABLE_BOOKING_COMMAND: ("reservations", "3.0.30", "auto_confirm"),
}


def birth_status_reading_problems(name, doc, floors):
    """The step that books explains the switch in the shape its read really answers — whatsapp_inbox#152.

    Three things, per language: the pinned `true`/`false` reading of the switch, the pinned reading
    of an empty answer, and none of the old `0`/`1` wording left beside them. Plus the floor: a
    family whose read only answers a boolean from some release on declares at least that release,
    or the hub offers the recipe to a Reservas that still answers `0`/`1`.
    """
    parts = name.split(".")
    lang = parts[1] if len(parts) >= 3 else ""
    problems = []
    for step in doc.get("steps", []):
        if step.get("kind") != "ai":
            continue
        commands = (step.get("tools") or {}).get("commands") or []
        prompt = prompt_of(step)
        for booking in sorted(BIRTH_STATUS_READING):
            if booking not in commands:
                continue
            for table, what in (
                (BIRTH_STATUS_READING, "what `true` and `false` of the switch mean"),
                (BIRTH_STATUS_EMPTY, "how to read the switch when it comes back empty"),
            ):
                sentence = table[booking].get(lang)
                if sentence is None or sentence not in prompt:
                    problems.append(
                        f"{name} step `{step.get('id')}` can book with `{booking}` and its prompt "
                        f"no longer says {what} («{sentence}»). The read answers `true`/`false`; "
                        f"a prompt that explains anything else leaves the model guessing which "
                        f"ending the customer gets"
                    )
            stale = RAW_FLAG_WORDING.search(prompt)
            if stale:
                problems.append(
                    f"{name} step `{step.get('id')}` still explains the switch as the raw `0`/`1` "
                    f"(«{stale.group(0)}»): the read answers `true`/`false` since reservations#54, "
                    f"and a prompt that says both lets the model read the stale half"
                )
            since = BIRTH_STATUS_BOOLEAN_SINCE.get(booking)
            if since is None:
                continue
            module_id, version, _field = since
            declared = floors.get(module_id)
            have = version_tuple(declared)
            if have is None or have < version_tuple(version):
                problems.append(
                    f"{name} step `{step.get('id')}` explains `{module_id}`'s switch as "
                    f"`true`/`false`, which it only answers from {version} on, and the family "
                    f"declares `{module_id}` at {declared}: raise it in "
                    f"`{name.split('.')[0]}.requires.json`, or the hub offers the recipe to a "
                    f"release whose answer the prompt does not describe"
                )
    return problems


BOOLEAN_PROJECTION = "{field}\\s*<>\\s*0\\s+AS\\s+{field}\\b"


def boolean_since_problems(definitions):
    """`BIRTH_STATUS_BOOLEAN_SINCE` names the FIRST release that answers the switch as a boolean.

    Read out of the neighbour's history, both ways: the settings query projects `<field> <> 0 AS
    <field>` at the pinned release, and does not one patch release below it. Returns `(problems,
    skipped)` — a history this machine cannot read is a skip, never a red.
    """
    problems, skipped = [], []
    for booking, (module_id, version, field) in sorted(BIRTH_STATUS_BOOLEAN_SINCE.items()):
        source = BIRTH_STATUS_SOURCE[booking]
        target = (definitions or {}).get(source)
        if target is None:
            skipped.append(f"`{source}` is not declared by any checkout here — {version} NOT verified")
            continue
        module_dir, qdef = target
        rel = qdef.get("sql")
        major, minor, patch = version_tuple(version)
        below = f"{major}.{minor}.{patch - 1}"
        pattern = re.compile(BOOLEAN_PROJECTION.format(field=re.escape(field)), re.IGNORECASE)
        for at, expected in ((version, True), (below, False)):
            sha, why = release_commit(module_dir, at)
            if sha is None:
                skipped.append(f"`{source}` at {at} could not be read ({why}) — {version} NOT verified")
                break
            blob, why = git_in(module_dir, "show", f"{sha}:{rel}")
            if blob is None:
                skipped.append(f"`{source}` at {at} could not be read ({why}) — {version} NOT verified")
                break
            if bool(pattern.search(SQL_COMMENT.sub(" ", blob))) != expected:
                problems.append(
                    f"`BIRTH_STATUS_BOOLEAN_SINCE` pins {module_id} {version} as the first release "
                    f"whose `{source}` answers `{field}` as a boolean, and at {at} it "
                    f"{'does not' if expected else 'already does'}: move the pin to the release "
                    f"that really made the change"
                )
    return problems, skipped

# ── «a rule with no recipe is a promise nothing keeps» ────────────────────────────────────────
#
# whatsapp_inbox#60. `BOOKING_RULES` is the table of everything this channel knows how to book
# unattended, and until this rule existed a row could sit in it with no document spending it: the
# wording pinned, `hour_choice_problems` green — silently, because that rule only judges documents
# that HAND the command — and the restaurant that connected its WhatsApp offered the two recipes of
# a hairdresser and nothing it could use. That is the issue exactly: not a broken template, a
# missing one, and every rule here was green over it.
#
# ONE family per booking, no more and no less (whatsapp_inbox#124). It used to be BOTH — an
# attended recipe and an unattended one — on the grounds that `flows/README.md` sold the choice and
# the business made it at install. The choice was never the business's to make twice: it had
# already made it in Citas («confirm automatically») and in Reservas (`auto_confirm`), and the pair
# only asked it again in words it could not check. Whichever the owner picked, the setting still
# decided what really happened.
def booked_families(docs):
    """`family -> every command its `ai` steps can call`, over the documents shipped in `flows/`."""
    out = {}
    for path, doc in docs:
        commands = out.setdefault(path.name.split(".")[0], set())
        for step in doc.get("steps", []):
            if step.get("kind") == "ai":
                commands.update((step.get("tools") or {}).get("commands") or [])
    return out


def shipped_recipe_problems(name, doc, booked):
    """Every booking `BOOKING_RULES` has a wording for really SHIPS, attended and unattended.

    A document rule that never reads the document, and for the same reason as
    `identity_field_problems`: what it needs is the ledger. As a one-off call in `main()` its
    deletion would be invisible — the templates that DO exist stay green, and the business whose
    recipe went missing is not a document this battery can miss, because there is no document.
    """
    problems = []
    for booking in sorted(BOOKING_RULES):
        shipped = sorted(f for f, commands in booked.items() if booking in commands)
        if not shipped:
            problems.append(
                f"{name}: `{booking}` has its wording pinned in BOOKING_RULES and no family in "
                f"`flows/` hands it, so the business that books with it has no recipe to install "
                f"and every other rule here stays green — they only judge the documents that "
                f"exist. Ship the recipe, or take the row out of the table"
            )
            continue
        if len(shipped) > 1:
            problems.append(
                f"{name}: `{booking}` is handed by {len(shipped)} families "
                f"({', '.join(shipped)}), and one use gets ONE recipe (whatsapp_inbox#124). Two "
                f"of them for a single decision is what the owner had to guess between, what made "
                f"every fix land twice, and what let one card promise the customer something the "
                f"other one did not do"
            )
    return problems


# ── «una reserva que no es suya» — la otra mitad de whatsapp_inbox#60 ─────────────────────────
#
# What this delivery DECLARES: the table families book, and they do not change and do not cancel,
# because `reservations` cannot tell whose booking it is. `schemas/reservation_set_status.json` and
# `schemas/reservation_update.json` are `additionalProperties: false` over `{reservation_id, …}`
# with no `channel` and no `customer_id`, and the handler only walks the state machine
# (`set_status_pure`) — it never asks whose row it is. The lookup that feeds them is a free search:
# `reservations.reservations.list` filters `guest_phone` and `guest_name` with `op: like`, so any
# `reservation_id` falls out of a fragment of somebody else's name.
#
# 🔴 **A declaration is not a control, and that is measured, not feared.** Handing the unattended
# table writer `…reservations.list` + `…reservations.set_status`, naming both in the prompt of BOTH
# languages and adding both grants left every rule in this battery GREEN over a recipe that cancels
# a stranger's table. It is the same shape that had to be closed by hand twice in this repo already
# (whatsapp_inbox#100, #103), and `moving_problems` says in so many words that it owes the table
# families nothing — so the hole had no rule at all. It is pinned here for the same reason it is
# pinned there: the fix that closes cancelling for chairs (pinning `payload` in the grant,
# hub#1623) has NOTHING to pin on a command that carries no such field.
#
# Reopening it is ERPlora/reservations#50 — `channel` + `customer_id` on those commands, the twin
# of appointments#140. The day it lands, these ops leave this table and get the treatment
# cancelling a chair already gets; not one day before.
UNOWNED_TABLE_OPS = {
    "commands": (
        "reservations.reservations.set_status",
        "reservations.reservations.update",
        "reservations.reservations.delete",
    ),
    "queries": ("reservations.reservations.list",),
}


def unowned_table_problems(name, doc):
    """No step that writes with NOBODY watching may touch a booking that already exists.

    Judged on every `ai` step and not on the table writer alone: the harm is the tool in the hands
    of a turn that EXECUTES, so a second step added later owes exactly the same. A step that forgot
    to say how it runs counts as «nobody is watching» — failing closed is the only direction in
    which getting it wrong is visible.

    Silent where a PERSON approves the write (`policy: "manual"` → `_flow_approvals`, and at the
    yes it runs exactly as proposed). That is the same split `moving_problems` makes for chairs,
    and it is what lets the attended family grow into changing and cancelling without touching this
    rule.
    """
    problems = []
    for step in doc.get("steps", []):
        if step.get("kind") != "ai" or step.get("policy") == "manual":
            continue
        tools = step.get("tools") or {}
        for where, ops in sorted(UNOWNED_TABLE_OPS.items()):
            for op in ops:
                if op not in (tools.get(where) or []):
                    continue
                problems.append(
                    f"{name} step `{step.get('id')}` runs with nobody watching and is handed "
                    f"`{op}`: `reservations` never checks whose booking it is — those commands "
                    f"carry no `channel` and no `customer_id`, and the query that finds the id "
                    f"searches `guest_name` and `guest_phone` with `op: like` — so a stranger's "
                    f"table is one sentence of prompt away from being moved or cancelled from "
                    f"this chat. Leave it to the attended family, where a person approves the "
                    f"write, until ERPlora/reservations#50 lands"
                )
    return problems


def hour_choice_problems(name, doc):
    """In the unattended family, the step that can BOOK says, in its own language, that it never
    picks the hour.

    whatsapp_inbox#58, reviewer mutant N2. With `policy: auto` and nobody at the salon, the one
    thing standing between the customer and an appointment at an hour they never asked for is a
    paragraph of the prompt — «you never choose the hour, they do». Reword it away and nothing
    changes shape: the document validates, the grants match, every other rule here is green, and
    the model starts «helpfully» sliding people to the nearest free slot. The forums the issue
    cites are unanimous about how that ends (double bookings, no-shows, the chair AND the customer
    lost), which is why the attended sibling can leave it to a person and this family cannot.

    Judged per language, because the model reads the prompt in the language it is written in: a
    Spanish document carrying only the English sentence has the rule for nobody who reads it.
    Silent on every other family, and on the steps that cannot book.
    """
    if not is_unattended(name):
        return []
    parts = name.split(".")
    lang = parts[1] if len(parts) >= 3 else ""
    problems = []
    for step in doc.get("steps", []):
        if step.get("kind") != "ai":
            continue
        commands = (step.get("tools") or {}).get("commands") or []
        for booking, wording in sorted(BOOKING_RULES.items()):
            if booking not in commands:
                continue
            sentence = wording.get(lang)
            if sentence is None:
                problems.append(
                    f"{name} step `{step.get('id')}` can book unattended with `{booking}` and this "
                    f"battery has no wording of the hour rule for language `{lang}`: add the "
                    f"translation to `BOOKING_RULES` in the same commit, or the rule is a promise "
                    f"this document does not make to the people who read it"
                )
            elif sentence not in prompt_of(step):
                problems.append(
                    f"{name} step `{step.get('id')}` can book unattended with `{booking}` and its "
                    f"prompt no longer says «{sentence}»: with `policy: auto` and nobody at the "
                    f"business, that sentence is the only thing keeping the model from booking "
                    f"people into hours they never asked for. If the wording changed, change "
                    f"`BOOKING_RULES` with it — it is the contract of the `-unattended` family, "
                    f"not a nicety"
                )
    return problems


# ── «moving is one call, never two» ───────────────────────────────────────────────────────────
#
# whatsapp_inbox#74. Of the three things a customer asks a salon by WhatsApp — book, move, cancel
# — moving is the one most often asked for, and it was the one the automation answered with «one
# of us will get back to you». `appointments.appointments.reschedule` moves the appointment ROW:
# the same customer, the same professional, a new time, with the salon's own rules (minimum
# notice, maximum advance, blocked periods) deciding whether it may.
#
# The tempting substitute — cancel it and book again — is not the same operation, and it is not a
# worse-but-equivalent one. It spends the customer's cancellation allowance, it loses the row the
# salon had in front of her, and when the second call then fails (the slot went in between, or
# `check` answers `held`) the customer who wrote asking to KEEP her hour is left with nothing at
# all. That is the shortcut this rule exists to make expensive: both calls are already in the same
# step's hands for the other branches, so it is always one sentence away.
MOVE_COMMAND = "appointments.appointments.reschedule"
OWNED_APPOINTMENTS_QUERY = "appointments.appointments.list_for_customer"
# The ADDRESS BOOK, searchable by name (`customers.list` declares `search: [name, …]` and a
# `name` filter with `op: like`, so on the wire `f_name`/`search` reach whoever holds it).
# Harmless in a hub screen; not in the hands of a model that is reading a stranger's WhatsApp.
DIRECTORY_QUERY = "customers.list"
# The read that answers «whose number is this?» — and the ONLY one a resolver may be
# (whatsapp_inbox#165). `customers.list` filters `phone` with a LIKE over the raw column, so the
# number WhatsApp gives (`34600111222`) never finds a card the salon typed the way people type
# phones in Spain (`600 111 222`, `+34 600-111-222`): the recipe answered «not on file», created a
# SECOND card for a customer of years, and booked on the new one. `customers.by_phone`
# (customers#79) compares NUMBERS — the same rule the inbox listeners apply since whatsapp_inbox#162
# — and takes only `phone`, so it is not a search box either.
RESOLVER_QUERY = "customers.by_phone"
# What the trigger carries and no model can touch: the phone the message came FROM. It is mapped
# in `triggers[].input`, so it reaches a step as `{{input.from}}` — the one identity in this run
# that WhatsApp itself vouched for.
TRUSTED_PHONE = "input.from"

# `command -> {payload field: the ONE value a template of this module may ever send}`.
#
# hub#1623 (ADR-0456): a `command` grant may FIX part of the payload, and the hub then refuses the
# call that sends anything else — **and the call that omits the field**, which is the half that
# matters here, because `appointments`' own `schemas/appointment_cancel.json` defaults `channel` to
# `staff`. So «say nothing» is the WIDE cancellation: the one that skips whether customers may
# cancel at all, how much notice they owe, and the check that whoever asks is the person on the
# appointment (`cancel_appointment_pure`).
#
# The row exists because the only thing that used to hold the narrow value was a PARAGRAPH OF
# PROMPT, written for a model that reads a stranger's WhatsApp message in the same turn. A
# permission is a permission; prose is not one, however emphatic (whatsapp_inbox#100).
PINNED_COMMAND_PAYLOAD = {
    CANCEL_COMMAND: {"channel": "customer"},
    # And MOVING, for the same reason and with the same default (whatsapp_inbox#105): since
    # appointments#144 `reschedule` takes `channel` + `customer_id` and runs the same
    # `customer_identity_refusal`, and its `channel` also defaults to `staff`. So «say nothing» is
    # the WIDE move — no minimum notice, no maximum advance, and no check that the appointment
    # belongs to whoever wrote in.
    MOVE_COMMAND: {"channel": "customer"},
    # And BOOKING, where the omitted default does not widen a permission but breaks a PROMISE
    # (whatsapp_inbox#124). `appointments`' `born_confirmed` is `auto_confirm_online` AND the
    # booking saying it was made by the customer; `schemas/appointment_create.json` defaults
    # `booked_online` to `false`, so a payload that leaves it out is born `pending` on EVERY hub,
    # including the salon that switched «confirm automatically» on and was told this channel would
    # stop making it accept bookings one by one. The switch would do nothing and nothing would say
    # so: the document parses, the grant covers the command, the appointment is created.
    BOOKING_COMMAND: {"booked_online": True},
}

# What the WIDE default actually costs, per command — the sentence `unpinned_command_problems`
# quotes. A table because the three harms are different, and a message that describes the wrong one
# sends whoever reads it looking for a bug that is not there.
PIN_HARM = {
    CANCEL_COMMAND: (
        "omitting the field is enough to cancel AS THE SALON — no notice window, no «may "
        "customers cancel», no check of whose appointment it is"
    ),
    MOVE_COMMAND: (
        "omitting the field is enough to move the hour AS THE SALON — no minimum notice, no "
        "maximum advance, and no check that the appointment belongs to whoever wrote in"
    ),
    BOOKING_COMMAND: (
        "omitting the field makes the appointment be born `pending` on every hub, whatever the "
        "salon set in «confirm automatically» — so the switch does nothing and the recipe tells "
        "the customer the opposite of what the diary holds"
    ),
}


def unpinned_command_problems(name, doc, pins):
    """A command handed to a step NOBODY watches carries its narrow value in the GRANT, not in the
    prompt.

    The rodeo this closes needs no bug and no jailbreak. The customer writes «cancel it»; the model
    that answers her also writes the payload of `appointments.appointments.cancel`; and the salon's
    permission says «may cancel appointments», every argument included. Leave `channel` out — which
    is easier than contradicting the prompt, because it is what a model does when a paragraph is
    long — and `appointments` reads its own default, `staff`. The cancellation goes through as the
    SALON's, so no notice window applies, no «may customers cancel?» setting applies, and nobody
    checks that the person asking is the person on the appointment. Nothing downstream refuses it:
    the command was granted and the payload is valid.

    `PINNED_COMMAND_PAYLOAD` is the answer, and what this rule holds is that the pin is really in
    the file — because the pin is one JSON key deep in a sidecar nobody reads out loud, and the day
    it goes missing every other rule here stays green: the grant still covers the tool, the prompt
    still says `customer`, the document still parses.

    ✅ **And since hub#1654 the declaration IS what is enforced.** `FlowTemplateGrant`
    (`crates/runtime/src/manifest.rs`) was `{kind, value}` until then, so serde dropped `payload`
    without a word and the factory recipe installed with the WIDE permission while this rule sat
    green. It now carries the pin to the hub, where `check_payload_pin` (hub#1623) refuses a payload
    that omits or contradicts a pinned field — at the door the dispatcher goes through and at the
    approval door too. Nothing here had to change when it landed, which was the point of guarding
    the declaration in the first place.

    🔴 **Every `ai` step that is handed the command owes the pin, whoever is watching**
    (whatsapp_inbox#107). The rule used to skip steps under `policy: "manual"`, on the grounds that
    a person approves the write in the tray before it happens. The market says that is the wrong
    frontier and nine references say it the same way — Mindbody bills «cancel» and «override the
    cancellation policy» as SEPARATE permissions, WooCommerce Bookings gives the admin a different
    door from the customer's, and Business Central states it outright: permissions decide what may
    be done, workflows decide whether a permitted action needs review. They are different controls,
    and one does not stand in for the other.

    It matters here for a reason anyone can check: what the salon approves in the tray is a DRAFT
    FOR THE CUSTOMER, not a payload. Nothing in that screen says which `channel` the cancellation
    will carry, so the review cannot be the thing that keeps it narrow. And the pin loses nothing
    the attended recipe actually does — its own document only ever cancels for the customer who
    wrote in, and the salon's legitimate way to cancel on its own account is the Appointments
    screen with its own role, not a stranger's WhatsApp thread.

    The hub reads it per step rather than per policy too: `check_command_grant` runs at the
    approval door (`flows_api.rs`) and not only in the dispatcher (`commands.rs`), so a pin that
    gets there survives the tray instead of being redundant with it — «that gets there» being the
    hole hub#1654 closes, above.

    Deterministic `kind: command` steps stay out: there the payload is mapped by the DOCUMENT, so
    no model chooses the channel and pinning would break a template that legitimately cancels for
    the salon.

    Silent when the grant is missing altogether: `main()` already compares needed against declared
    and says so in its own words, and a second complaint about the same absent line would send
    whoever reads it looking for a pin on a grant that is not there.
    """
    problems = []
    for step in doc.get("steps", []):
        if step.get("kind") != "ai":
            continue
        handed = ((step.get("tools") or {}).get("commands")) or []
        for cname in handed:
            required = PINNED_COMMAND_PAYLOAD.get(cname)
            if not required:
                continue
            fixed = pins.get(cname)
            if fixed is None:
                continue  # no grant at all: main() is already saying that, louder
            for field, value in sorted(required.items()):
                if fixed.get(field) == value:
                    continue
                sent = (
                    f"fixes `{field}` = `{fixed[field]}`"
                    if field in fixed
                    else "fixes nothing"
                )
                harm = PIN_HARM.get(
                    cname, "the caller gets to choose the default, which is what the pin is for"
                )
                problems.append(
                    f"{name} hands `{cname}` to the model in `{step.get('id')}`, and its grant "
                    f"{sent}: the payload is written by a model reading a stranger's message, so "
                    f"`{field}` = `{value}` has to be pinned in "
                    f"`{family_of(name)}.grants.json` (`payload`, hub#1623). Left open, "
                    f"{harm}. A review does not close it: whoever approves reads a draft for the "
                    f"customer, not a payload"
                )
    return problems


# ── «a diary is somebody's» — whatsapp_inbox#119 ───────────────────────────────────
#
# `query -> the payload field that says WHOSE`.
#
# hub#1662 widened hub#1623 to reads: a grant may FIX part of the payload on a `query` too, and the
# fixed value may NAME a place in the run (`steps.<id>.<field>`) instead of being a literal — which
# is the only shape an identity can take, because who this run is about is not known until the run
# resolves her.
#
# The field is named here and the VALUE is derived from the document, on purpose: what the pin has
# to point at is the deterministic resolver `own_customer_only_problems` already demands, and a
# constant repeating its step id would go stale the day somebody renames the step — quietly, and in
# the direction that WIDENS the permission.
PINNED_QUERY_IDENTITY = {OWNED_APPOINTMENTS_QUERY: "customer_id"}


def declared_query_pins(path):
    """`query -> the payload fields its grant FIXES`, `{}` for a grant that fixes none.

    The read-side twin of `declared_command_pins`, and separate from it for the reason the hub keeps
    them separate: `Authority.pins` is keyed by the PAIR `(kind, value)`, because a read and a write
    that happen to share a name must not inherit each other's restriction.
    """
    body = json.loads(path.read_text())
    items = body["grants"] if isinstance(body, dict) else body
    return {g["value"]: (g.get("payload") or {}) for g in items if g.get("kind") == "query"}


def unpinned_query_problems(name, doc, pins):
    """A diary handed to a model is granted for ONE customer, not for anybody — whatsapp_inbox#119.

    `own_customer_only_problems` took the address book out of the model's hands and put a
    deterministic resolver in front of the diary. What it could NOT do at the time it was written is
    say so in the permission: a grant pinned payload values only on a `command`, so
    `list_for_customer` was granted by NAME and «may read a diary» meant «may read ANYBODY's diary».
    The only thing left holding the boundary was a paragraph of prompt — «One customer, and only
    that one» — addressed to a model that is reading a stranger's WhatsApp message in the same turn.
    A paragraph is not a door.

    hub#1662 is the door. The pin travels in the sidecar (hub#1654), the screen keeps it when the
    owner touches another permission (ERPlora/flows#108), and `check_query_grant` resolves
    `steps.<resolver>.id` against the run and refuses every other `customer_id` with
    `flow.grant_payload_denied` — including the run where the resolver found nobody, which publishes
    `null` and is denied rather than widened.

    What this rule holds is that the pin is really in the file, because it is one JSON key deep in a
    sidecar nobody reads out loud and the day it goes missing every other rule here stays green: the
    grant still covers the read, the prompt still says «only that one», the document still parses.

    Three things it deliberately does NOT complain about, each because something else says it better:

    * **no grant at all** — `main()` already compares needed against declared, and a second
      complaint would send whoever reads it hunting for a pin on a grant that is not there;
    * **no resolver in the document** — `own_customer_only_problems` owns that red, and it is a
      bigger one: without a resolver there is no id to pin TO;
    * **a deterministic `kind: query` step reading the diary** — there the params are mapped by the
      DOCUMENT, so no model chooses whose diary it is.

    🔴 And the pin has to be a BARE path. `check_pin_value` refuses one carrying `{{…}}`
    (`flow.invalid_grant_payload`), and that refusal is ALL-OR-NOTHING: `PUT …/grants` rejects the
    whole list, so the recipe installs with no permissions whatsoever. A pin written as a template
    does not degrade to a wide grant — it takes the recipe down with it.
    """
    problems = []
    resolvers = [(i, s.get("id")) for i, s in _query_steps(doc, RESOLVER_QUERY)]
    for index, step in enumerate(doc.get("steps", [])):
        if step.get("kind") != "ai":
            continue
        handed = ((step.get("tools") or {}).get("queries")) or []
        for qname in handed:
            field = PINNED_QUERY_IDENTITY.get(qname)
            if not field:
                continue
            fixed = pins.get(qname)
            if fixed is None:
                continue  # no grant at all: main() is already saying that, louder
            # Only a resolver that has already RUN can be pinned to: `steps.x` of a step that has
            # not run resolves to `null`, and `resolve_pin` refuses a pin that resolves to nothing
            # (`flow.grant_payload_denied`). A pin aimed forwards denies every call, for everyone.
            before = [sid for i, sid in resolvers if i < index]
            if not before:
                continue  # `own_customer_only_problems` owns this red, and it is the bigger one
            # …and of those, the one THIS step already works with. The prompt sends
            # `{{steps.<id>.id}}` as the `customer_id`, so pinning any OTHER resolver denies the
            # call the moment the two differ — which is exactly the run where the customer was
            # created a step ago and the earlier resolver found nobody.
            named = [sid for sid in before if "{{steps." + str(sid) + ".id}}" in (prompt_of(step) or "")]
            wanted = sorted(f"steps.{sid}.id" for sid in (named or before))
            if fixed.get(field) in wanted:
                continue
            sent = (
                f"fixes `{field}` = `{fixed[field]}`" if field in fixed else "fixes nothing"
            )
            problems.append(
                f"{name} hands `{qname}` to the model in `{step.get('id')}`, and its grant "
                f"{sent}: a read is granted by NAME, so that permission is «may read ANYBODY’s "
                f"diary» — day, hour and professional of whoever the model puts in `{field}`, "
                f"while it reads a stranger’s message. Pin it in "
                f"`{name.split('.')[0]}.grants.json` (`payload`, hub#1662) to `{wanted[0]}`, the "
                f"customer this run resolved from the phone WhatsApp itself vouched for. A BARE "
                f"path, never `{{{{…}}}}`: the hub refuses a pin with templates in it, and that "
                f"refusal takes the whole permission list with it"
            )
    return problems


# ── «una instrucción no se pierde en la traducción» — whatsapp_inbox#112 ──────────────────────
#
# The recipes are written in English and translated into Spanish, and until this rule nothing held
# the two texts to saying the SAME THING. What they DO is checked to death — steps, triggers, tools,
# grants — but the instructions the model reads are free prose, so a paragraph that never made it
# into one of the four documents leaves every rule in this battery green.
#
# It is not a fear, it is what happened (whatsapp_inbox#108): the notice-window warning was added to
# the four booking templates and in one of them it did not land. The battery passed, `erplora
# validate` passed, and it was caught by opening the four files by hand. In production that is a
# Spanish business whose automation skips a rule its English twin respects — and the customer is the
# one who finds out, at the door, after choosing.
#
# So the same thing is done here that `BOOKING_RULES` and `TAP_WORDS` already do for one sentence
# each, only generalised: what may NOT be lost goes in a table, by family and by language, and a
# rule walks the documents demanding it. Adding a safety instruction becomes adding a row; losing it
# in one language becomes a red.
#
# What this is NOT: a word-by-word comparison of the two prompts. A real translation splits
# sentences, reorders them and moves them between steps — all three happen in these files. Only the
# sentence that carries the RULE is pinned, and it is looked for anywhere in the document.
PINNED_INSTRUCTIONS = {
    # whatsapp_inbox#124: the rows that guarded the attended halves went with the documents
    # themselves. `missing_instruction_problems` is anchored against what really ships in BOTH
    # directions, so a row outliving its recipe is a red here — which is the whole point: the
    # table cannot quietly keep guarding a file nobody installs any more.
    "appointment-from-whatsapp": (
        (
            "why `channel` is `customer`",
            {
                "en": "That `channel` is not decoration: it is what makes the salon's OWN rules apply",
                "es": "Ese `channel` no es un adorno: es lo que hace que se apliquen las reglas PROPIAS del salón",
            },
        ),
        (
            "who is asking when MOVING, not only when cancelling",
            {
                "en": "Moving says who is asking too: `channel` set to `customer` and the `customer_id` you looked up from THEIR phone number",
                "es": "Mover también dice quién lo pide: `channel` puesto a `customer` y el `customer_id` que buscaste por SU teléfono",
            },
        ),
        # whatsapp_inbox#124. The pin in `appointment-from-whatsapp.grants.json` REFUSES the call
        # that omits `booked_online` (`check_payload_pin`), so the prompt has to ORDER it or every
        # booking this channel makes dies at the door with the customer told nothing. Pinned here
        # rather than left to the prose because it is one clause inside a numbered instruction, and
        # that is exactly what a translation drops: with it gone from the Spanish document only the
        # Spanish half stops booking, and every other rule here stays green over it.
        (
            "the booking says the customer made it herself",
            {
                "en": "`booked_online` set to `true`",
                "es": "`booked_online` puesto a `true`",
            },
        ),
    ),
    # whatsapp_inbox#125. It carries no prompt at all — there is no model in it — so the honest
    # row is the empty one the rule itself asks for, rather than a name left out that reads as an
    # oversight.
    "appointment-confirmed-to-whatsapp": (),
    "reservation-from-whatsapp": (
        (
            "never a blocked day, never a window without room",
            {
                "en": "Never offer a time on a blocked day, and never offer a window with less room than they need.",
                "es": "No ofrezcas nunca una hora de un día bloqueado, ni una franja con menos sitio del que necesitan.",
            },
        ),
        (
            "never a day outside the restaurant's advance window",
            {
                "en": "never offer a day OUTSIDE that advance window",
                "es": "no ofrezcas nunca un día FUERA de esa ventana de antelación",
            },
        ),
    ),
}


def missing_instruction_problems(name, doc, families):
    """Every instruction `PINNED_INSTRUCTIONS` names is really in the document, IN ITS LANGUAGE.

    Judged per language, because the model reads the prompt in the language it is written in: a
    Spanish document that carries only the English sentence has the rule for nobody who reads it.
    And judged per FAMILY, because the same promise is worded differently by the recipe that books
    a chair and the one that books a table — the salon orders `booked_online`, the restaurant has
    no pin to order — and flattening the two into one wording would force a document to say
    something it has no reason to say.

    Looked for anywhere in the document rather than in a named step, on purpose: which step holds a
    sentence is exactly what a legitimate rewrite moves around, and a rule that also pins the step
    turns every honest edit into a red — which is how a guard stops being read.

    The table is anchored against what really ships (`families`) IN BOTH DIRECTIONS, the hole
    `shipped_recipe_problems` closes for `BOOKING_RULES`. Rename a recipe and the row keeps guarding
    a document that no longer exists, with this battery green, because every rule here only judges
    the documents that are there. And the mirror, which is the one that matters: delete the row and
    the recipe it guarded keeps shipping, unguarded, also green — a guard that can be switched off
    by deleting a line is not a guard, it is a comment. Measured in review, not feared: dropping
    `reservation-from-whatsapp-unattended` and then losing the advance-window sentence from its
    Spanish document — whatsapp_inbox#108 again, in the half nobody is watching — left this battery
    at `EXIT=0`. So every recipe in `flows/` owes a row. A recipe that carries no safety sentence
    owes an EMPTY one (`"family": ()`): the decision that there is nothing to keep is written down
    where the next person can read it, instead of looking exactly like a row somebody deleted.
    """
    problems = []
    for family in sorted(PINNED_INSTRUCTIONS):
        if family not in families:
            problems.append(
                f"{name}: `PINNED_INSTRUCTIONS` pins instructions for `{family}`, and no document "
                f"in `flows/` belongs to that family: the row guards nothing and reads as if it "
                f"did. Point it at the family that shipped, or take it out"
            )
    for family in sorted(set(families) - set(PINNED_INSTRUCTIONS)):
        problems.append(
            f"{name}: `{family}` ships in `flows/` and has no row in `PINNED_INSTRUCTIONS`, so "
            f"nothing here holds its two translations to saying the same thing — which is the "
            f"whole of whatsapp_inbox#112, and it stays green. Deleting a row has to be as loud "
            f"as deleting the sentence, or the guard is one edit away from being a comment. Give "
            f"it the sentences it may not lose, or, if it carries none, write that down with an "
            f"empty row (`\"{family}\": ()`)"
        )
    parts = name.split(".")
    lang = parts[1] if len(parts) >= 3 else ""
    for label, wording in PINNED_INSTRUCTIONS.get(parts[0], ()):
        sentence = wording.get(lang)
        if sentence is None:
            problems.append(
                f"{name} is pinned to say «{label}» and this battery has no wording of it for "
                f"language `{lang}`: add the translation to `PINNED_INSTRUCTIONS` in the same "
                f"commit that ships the document, or the instruction is a promise this language "
                f"does not make"
            )
            continue
        if any(sentence in prompt_of(step) for step in doc.get("steps", [])):
            continue
        problems.append(
            f"{name} no longer says «{label}»: no prompt in it carries «{sentence}». That "
            f"sentence is a rule the model has no other way of knowing — nothing in the document, "
            f"the grants or the kernel says it — so the language that loses it gets an automation "
            f"that behaves differently from its twin, and everything here stays green while it "
            f"does. If the wording changed, change `PINNED_INSTRUCTIONS` with it"
        )
    return problems


MOVE_RULE = {
    "en": "Moving is one call, never two.",
    "es": "Mover es una sola llamada, nunca dos.",
}
# The order these templates carried while the branch did not exist. It is not dead prose left
# behind: it is an ORDER, and a model obeys the order over the tool list. A step handed
# `reschedule` whose prompt still says the automation cannot move keeps answering «somebody will
# get back to you» with the permission granted, asked of the owner, and spent on nothing — which
# is exactly what a half-applied fix for this issue looks like from the outside: green tests, and
# a customer who still cannot move her appointment.
CANNOT_MOVE = {
    "en": "this automation cannot do yet",
    "es": "esta automatización todavía no sabe hacer",
}
# The other stale order, and the one that outlived the branch it described (whatsapp_inbox#105).
# The attended recipe has moved appointments since whatsapp_inbox#74, and its MOVING section told
# the model WHY it had to be careful with the id: `reschedule` said nothing about who was asking,
# so `appointments` could not tell whose appointment it had been handed. That was true, and since
# appointments#144 (v1.1.73) it is FALSE — the command takes `channel` + `customer_id` and refuses
# a move of somebody else's appointment. A sentence like this one is worse than out of date: it
# tells the model the field it is about to send does not exist, which is the reading that ends
# with the move going out on the salon's own account.
MOVE_BLIND = {
    "en": "this operation says nothing about who is asking",
    "es": "esta operación no dice quién la pide",
}


def moving_problems(name, doc):
    """Both appointment families MOVE, and moving says who is asking — whatsapp_inbox#74, #105.

    Judged on the step that hands `BOOKING_COMMAND`, which is the appointment writer of both
    families: what a customer can ask this channel for is decided there, in one place. Silent on
    every other step and on any future template that does not book appointments at all (table
    reservations, whatsapp_inbox#60): they owe nothing here.

    🔴 **The split by `policy` is GONE, and that is the change this issue is** (whatsapp_inbox#105).
    The rule used to demand the opposite of each family — the attended one moved, the unattended one
    had to be UNABLE to and had to say so — and the reason was real while it lasted: `reschedule`
    took no `channel` and no `customer_id`, its handler never looked at whose appointment it was,
    and so the chain `customers.list` (searchable by name) → `list_for_customer` (takes any
    `customer_id`) → move was a stranger's hour changed with nobody in the loop. Since
    appointments#144 (v1.1.73) that is no longer the shape of the command: it carries the same two
    fields cancelling does and runs the same EXTRACTED guard, `customer_identity_refusal(channel,
    payload, row)`, so a move on the customer channel is refused when the appointment belongs to
    somebody else.

    What replaced the split is `PINNED_COMMAND_PAYLOAD` — the value is pinned in the GRANT, where
    the model cannot choose it — and that is a different rule with its own red, on purpose: this one
    holds the DOCUMENT, that one holds the sidecar. A review does not stand in for either
    (whatsapp_inbox#107): permissions decide what may be done, an approval tray decides whether a
    permitted thing needs a person, and one is not the other. So there is no family here that owes
    LESS: «can you change it to Thursday?» is the most common thing a customer writes, and the
    unattended salon — the one-chair salon whatsapp_inbox#58 ships for, with nobody reading — is
    precisely the one where «somebody will get back to you» is the wait this automation exists to
    remove.

    Five marks, each one edit away from being lost:

    * **it can move** — `MOVE_COMMAND` in `tools.commands`. This is the red the issue itself is;
    * **it can look up WHAT it is moving** — `OWNED_APPOINTMENTS_QUERY` in `tools.queries`. Not a
      nicety and not symmetry with cancelling: the id it moves has to come out of the diary of the
      customer resolved from her own phone number (whatsapp_inbox#103), because the pin makes
      `appointments` refuse a stranger's appointment only once it is ASKED, and asking with an id
      picked out of the message is a refusal the customer reads instead of an answer;
    * **the prompt says moving never becomes cancel-plus-book**, in the language it is written in,
      the same way and for the same reason `hour_choice_problems` pins its sentence: a model reads
      the prompt it was given, so a Spanish document carrying only the English sentence has the
      rule for nobody who reads it. A language this battery has no wording for is a document it
      cannot vouch for — the translation is added to `MOVE_RULE` in the same commit, or it does
      not ship;
    * **the old «it cannot» order is gone** — `CANNOT_MOVE`. Adding the tool and leaving the
      sentence is the half-fix that passes everything else here: a model obeys the order over the
      tool list, so the branch stays dead, the owner was asked for a permission nothing spends,
      and the customer still waits for a person;
    * **and the old «it cannot say who is asking» order is gone too** — `MOVE_BLIND`. Same failure
      one layer down, and the one this issue found in the UNNAMED_FAMILY family, which has moved
      appointments since whatsapp_inbox#74: its MOVING section still ordered that `appointments`
      cannot tell whose appointment it is. A model told the field does not exist does not send it,
      and a move with no `channel` is a move on the salon's own account — no minimum notice, no
      maximum advance, no check of whose hour it is.

    Silent about `policy` on purpose now: a document that forgets to declare one is judged exactly
    like its twins, so there is no reading of this file where forgetting a line buys a weaker rule.
    """
    parts = name.split(".")
    lang = parts[1] if len(parts) >= 3 else ""
    problems = []
    for step in doc.get("steps", []):
        if step.get("kind") != "ai":
            continue
        tools = step.get("tools") or {}
        if BOOKING_COMMAND not in (tools.get("commands") or []):
            continue
        sid = step.get("id")
        prompt = prompt_of(step)
        if MOVE_COMMAND not in (tools.get("commands") or []):
            problems.append(
                f"{name} step `{sid}` can book and cancel an appointment and cannot MOVE one "
                f"(`{MOVE_COMMAND}` is not in its `tools.commands`): «can you change it to "
                f"Thursday?» is the most common thing a customer writes and the only one this "
                f"channel answers with «somebody will get back to you», which is the wait the "
                f"automation exists to remove. Since appointments#144 the command carries "
                f"`channel` + `customer_id` and refuses a move of somebody else's appointment, so "
                f"there is nothing left for this family to wait for"
            )
            continue
        if OWNED_APPOINTMENTS_QUERY not in (tools.get("queries") or []):
            problems.append(
                f"{name} step `{sid}` can move an appointment and was never handed "
                f"`{OWNED_APPOINTMENTS_QUERY}`: the `customer_id` it sends has to be the one "
                f"resolved from HER phone number and the `appointment_id` has to come out of HER "
                f"diary, so an id taken from the message is refused by `appointments` "
                f"(`customer_identity_refusal`) and she reads a refusal instead of a new hour"
            )
        sentence = MOVE_RULE.get(lang)
        if sentence is None:
            problems.append(
                f"{name} step `{sid}` can move an appointment and this battery has no wording of "
                f"the «one call, never two» rule for language `{lang}`: add the translation to "
                f"MOVE_RULE in the same commit, or the rule is a promise this document does not "
                f"make to the model that reads it"
            )
        elif sentence not in prompt:
            problems.append(
                f"{name} step `{sid}` can move an appointment and its prompt no longer says "
                f"«{sentence}»: it holds both `{CANCEL_COMMAND}` and `{BOOKING_COMMAND}` for the "
                f"other branches, so cancelling and re-booking is always available as a shortcut "
                f"— and it spends the customer's cancellation allowance and leaves her with "
                f"NOTHING when the second call fails. If the wording changed, change MOVE_RULE "
                f"with it"
            )
        stale = CANNOT_MOVE.get(lang)
        if stale is not None and stale in prompt:
            problems.append(
                f"{name} step `{sid}` was handed `{MOVE_COMMAND}` and its prompt still orders "
                f"that moving is «{stale}»: the model obeys the sentence, not the tool list, so "
                f"the branch is dead, the owner was asked for a permission nothing spends, and "
                f"every other rule here stays green over it"
            )
        blind = MOVE_BLIND.get(lang)
        if blind is not None and blind in prompt:
            problems.append(
                f"{name} step `{sid}` was handed `{MOVE_COMMAND}` and its prompt still orders "
                f"that «{blind}»: since appointments#144 it does — `channel` + `customer_id`, the "
                f"same pair cancelling sends and the same guard. A model told the field is not "
                f"there omits it, and `channel` DEFAULTS to `staff`, so the move goes out on the "
                f"salon's own account: no minimum notice, no maximum advance, and no check of "
                f"whose appointment it is"
            )
    return problems


# What a release of `customers.by_phone` has to MENTION to read a number as one of the BUSINESS's
# country (customers#81, first published in customers 2.3.47): the core's `hub_settings` row keyed
# `country_code`. Before it the query let any 1-3 digit prefix through.
HOME_COUNTRY_MARKERS = frozenset({"hub_settings", "country_code"})


def home_country_match_problems(name, doc, floor_columns):
    """The customer this family finds by the number she writes from is one of the BUSINESS's
    country at the floor it declares — whatsapp_inbox#202.

    The recipes read `customers.by_phone` with `result: first` and book on that card. Until
    customers#81 the query let ANY 1-3 digit prefix through, so a French `33 600 111 222` writing
    to a Spanish salon came back as the local card `600 111 222` — and the appointment or the
    table went on a stranger's record. The inbox's own listeners re-decide every row
    (`same_number` in the handler); a recipe cannot, so the only thing between that stranger and
    the card is the floor: the hub OFFERS the recipe (hub#1611) only to copies of Customers at or
    above it.

    🔴 The release is judged by what its SQL MENTIONS (`HOME_COUNTRY_MARKERS`), and a release
    that does not mention them is a release that does not know the country — «unknown», never
    «probably fine». A floor nobody could read, or where the query is missing altogether, is
    somebody else's answer (`main()`'s skip and `floor_read_column_problems`) and stays silent.
    """
    problems = []
    names = floor_columns.get(RESOLVER_QUERY)
    if names is None or names is ABSENT_AT_FLOOR or HOME_COUNTRY_MARKERS <= names:
        return problems
    for _, step in _query_steps(doc, RESOLVER_QUERY):
        problems.append(
            f"{name} step `{step.get('id')}` finds the customer with `{RESOLVER_QUERY}`, and at "
            f"the floor this family declares that query does not read the business's country "
            f"(no {' + '.join(sorted(HOME_COUNTRY_MARKERS))}): somebody writing from ANOTHER "
            f"country with the same national digits is taken for the local customer and booked "
            f"on her card — raise `customers` in `{name.split('.')[0]}.requires.json` to the "
            f"release of customers#81 (2.3.47)"
        )
    return problems


def _query_steps(doc, query):
    """`(index, step)` of every deterministic `query` step (hub#954) reading `query`."""
    return [
        (i, s)
        for i, s in enumerate(doc.get("steps", []))
        if s.get("kind") == "query" and s.get("query") == query
    ]


def own_customer_only_problems(name, doc):
    """A model reading a stranger's message never holds the ADDRESS BOOK — whatsapp_inbox#103.

    The chain this closes needs no bug and no jailbreak, only the two reads these templates were
    already granted: `customers.list` is searchable by NAME, so «what has María got booked?»
    resolves a stranger to her `id`; `list_for_customer` takes ANY `customer_id`, so that id
    returns her diary — day, hour, professional, `notes` and `internal_notes`; and what the step
    reads is what the step writes back, to whoever wrote in. Nothing downstream can refuse it: a
    read is not a write, so no approval tray sees it, and `appointments` is answering a question
    it was asked correctly. The only thing in the way was a paragraph of prompt telling the model
    to search by phone — which is the same «control» whatsapp_inbox#100 and hub#1623 exist to say
    is not one.

    🔴 **It could not be closed the way the write side is — until hub#1662.** A grant pinned
    payload values (hub#1623) on a `command` only: `crates/runtime/src/flows/grants.rs` refused a
    `payload` on any other kind with `flow.invalid_grant_payload`, because `check_command_grant`
    was the one gate handed a payload and a restriction nothing applies is worse than none. Both
    links here are `query` grants, so there was nothing to pin and taking the reads away instead
    would have taken cancelling with them. hub#1662 widened it: `check_query_grant` resolves a pin
    against the run, and `unpinned_query_problems` (whatsapp_inbox#119) now holds the diary read to
    naming the resolver this rule installs. The four marks below stay — the pin is a fifth lock on
    the same door, not a replacement: without a resolver in the document there is no id to pin TO.

    What closes it is moving the LOOKUP out of the model's hands. The kernel already has the
    shape: a `query` step (hub#954) is a deterministic read whose params are mapped by the
    DOCUMENT, not chosen by a model — and `{{input.from}}` is the phone WhatsApp itself vouched
    for. Resolve the customer there, and the only `customer_id` that exists in the run is the one
    the number belongs to. Four marks, each of them one edit away from being lost:

    * **the model is never handed the address book** — `DIRECTORY_QUERY` out of every `ai` step's
      `tools.queries`. This is the red the issue is: leave it in and every other mark here is
      decoration, because the model can resolve anybody by name whatever the prompt says;
    * **whoever can read a diary has a deterministic resolver BEFORE it** — a `kind: query` step
      over `RESOLVER_QUERY` earlier in the document. «Earlier» is not pedantry: `steps.x` of a
      step that has not run resolves to `null` (`resolve_path`), so a resolver placed after the
      reader hands it nothing and the model improvises again;
    * **that resolver is keyed on the phone and on nothing a model wrote** — every param
      templated from `input.`, and none of them reading `steps.` . A resolver fed
      `{{steps.know_the_customer.text}}` is the same hole with an extra step in it, and it would
      pass the two marks above;
    * **and the reader actually USES it** — `{{steps.<resolver>.id}}` named in the prompt.
      Without this the fix is only a restriction: the step has no customer, so it invents one or
      answers nothing, and «closed the hole» would mean «broke cancelling».

    Silent on documents that read no diary and hold no address book: a template that books
    nothing for a named person owes nothing here.
    """
    problems = []
    steps = doc.get("steps", [])
    resolvers = _query_steps(doc, RESOLVER_QUERY)

    # Mark 6 (whatsapp_inbox#165): the number is looked up as a NUMBER. A `query` step that feeds
    # the trusted phone to the address book is a resolver in every way but the one that matters —
    # `customers.list` compares the raw text with a LIKE, so a card typed `600 111 222` never
    # answers `34600111222`, the recipe believes she is new, and a second card is born for a
    # customer of years with the booking hung on it. Named here because the document parses, the
    # grant covers the read, and without this mark every other one stays green.
    for _, step in _query_steps(doc, DIRECTORY_QUERY):
        if TRUSTED_PHONE in json.dumps(step.get("params") or {}, ensure_ascii=False):
            problems.append(
                f"{name} step `{step.get('id')}` looks the customer up by her number with "
                f"`{DIRECTORY_QUERY}`, which filters `phone` as TEXT: a card the business typed "
                f"`600 111 222` or `+34 600-111-222` never matches `34600111222`, so a customer on "
                f"file is taken for a new one and gets a second card. Read `{RESOLVER_QUERY}` with "
                f"`phone` = `{{{{{TRUSTED_PHONE}}}}}` — it compares numbers"
            )

    # Mark 5, and the one that caught a real bug in this very commit: a resolver ANSWERS in
    # `{{steps.<id>.…}}`, and the braces are the whole mechanism. Written with one brace the
    # runtime never resolves it (`resolve_path` is only reached from `{{…}}`), so the model is
    # handed the literal text `{steps.find_customer.id}`, finds no id in it, and goes back to
    # deciding who this run is about — with every other mark here still green, because the step
    # LOOKS wired. The reservation templates have no diary read, so mark 4 does not cover them:
    # this one is owed by every resolver in every family.
    for index, step in enumerate(steps):
        if step.get("kind") != "query" or step.get("query") != RESOLVER_QUERY:
            continue
        sid = step.get("id")
        later = json.dumps(steps[index + 1:], ensure_ascii=False, sort_keys=True)
        if "{{steps." + str(sid) + "." not in later:
            problems.append(
                f"{name} resolves the customer in `{sid}` and no later step ever reads "
                f"`{{{{steps.{sid}.…}}}}`: the answer is fetched and dropped. Either a step is "
                f"meant to use it — and then the hole is still open, because whoever books is "
                f"choosing the customer some other way — or the reference lost a brace, which "
                f"reads as plain text to the model and resolves to nothing. A grant is spent "
                f"either way"
            )

        # The same reference, HALF-WRITTEN. `{{steps.x.id}}` is the whole mechanism; `{steps.x.id}`
        # is plain text the runtime never resolves (`resolve_path` is only reached from `{{…}}`),
        # so the model is handed the words and goes straight back to choosing the customer itself.
        # Neither mark above catches it on its own: mark 5 is satisfied whenever the resolver is
        # ALSO read correctly somewhere else (`.found`, `.count`), and mark 4 below only runs for
        # steps that read a diary — which the TABLE families (whatsapp_inbox#104) never do. So in
        # exactly those four documents the one reference carrying the identity could sit in the
        # prompt as plain text with the battery green. Not hypothetical: `str.format` produced this
        # shape while these very templates were being written.
        for broken in sorted(
            set(re.findall(r"(?<!\{)\{steps\." + re.escape(str(sid)) + r"\.[A-Za-z0-9_]+\}", later))
        ):
            problems.append(
                f"{name} names `{broken}` with ONE brace: the runtime resolves `{{{{…}}}}` and "
                f"nothing else, so `{sid}` is read and the step is handed that text verbatim "
                f"instead of the value. It LOOKS wired and resolves to nothing, which is how the "
                f"reference that carries the customer's identity goes missing with every other "
                f"mark still green"
            )

    for index, step in enumerate(steps):
        if step.get("kind") != "ai":
            continue
        sid = step.get("id")
        tools = step.get("tools") or {}
        queries = tools.get("queries") or []

        if DIRECTORY_QUERY in queries:
            problems.append(
                f"{name} step `{sid}` hands the model `{DIRECTORY_QUERY}`, which searches the "
                f"address book by NAME (`f_name`/`search`). Steered by a stranger's message that "
                f"is «find María» → her `id` → `{OWNED_APPOINTMENTS_QUERY}` → her diary, notes "
                f"and internal notes, written straight back to whoever asked. A `query` grant "
                f"cannot pin its params (`flow.invalid_grant_payload`), so the lookup has to "
                f"leave the model: resolve the customer in a `kind: query` step keyed on "
                f"`{{{{{TRUSTED_PHONE}}}}}` and hand the step the id, not the search"
            )

        if OWNED_APPOINTMENTS_QUERY not in queries:
            continue

        earlier = [(i, s) for i, s in resolvers if i < index]
        if not earlier:
            problems.append(
                f"{name} step `{sid}` can read one customer's whole diary with "
                f"`{OWNED_APPOINTMENTS_QUERY}` and no `kind: query` step resolved that customer "
                f"before it: the `customer_id` can only come from the model, so it is whoever the "
                f"message named. Add a deterministic read of `{RESOLVER_QUERY}` keyed on "
                f"`{{{{{TRUSTED_PHONE}}}}}` ahead of this step"
            )
            continue

        for _, resolver in earlier:
            rid = resolver.get("id")
            params = resolver.get("params") or {}
            if not params:
                problems.append(
                    f"{name} step `{rid}` resolves the customer with `{RESOLVER_QUERY}` and "
                    f"passes NO params: that is the whole address book, and its first row is "
                    f"somebody. Key it on `{{{{{TRUSTED_PHONE}}}}}`"
                )
                continue
            for key, expr in sorted(params.items()):
                text = expr if isinstance(expr, str) else json.dumps(expr, sort_keys=True)
                if "{{steps." in text or text.startswith("steps."):
                    problems.append(
                        f"{name} step `{rid}` resolves the customer with `{RESOLVER_QUERY}` and "
                        f"takes `{key}` from another step's output (`{text}`). If that step is an "
                        f"`ai` one, the model is choosing who this run is about again — the "
                        f"lookup moved, the hole did not. Key it on `{{{{{TRUSTED_PHONE}}}}}`"
                    )
            if not any(
                TRUSTED_PHONE in (expr if isinstance(expr, str) else "")
                for expr in params.values()
            ):
                problems.append(
                    f"{name} step `{rid}` resolves the customer with `{RESOLVER_QUERY}` and "
                    f"never reads `{TRUSTED_PHONE}`: it is keyed on "
                    f"{json.dumps(params, sort_keys=True)}, so it answers about somebody the "
                    f"phone number never picked out. The trigger's own `from` is the only "
                    f"identity in this run WhatsApp vouched for"
                )

        prompt = prompt_of(step)
        # The DOUBLE brace is the check, not `steps.<id>.id` as a substring: `{steps.x.id}` with
        # one brace contains it and resolves to nothing, so a substring match reads a broken
        # reference as a working one. Mark 5 does not cover this either when the same resolver is
        # read correctly elsewhere (`.found`, `.count`) and only `.id` — the one that carries the
        # identity — lost its braces. Measured: that mutant SURVIVED both marks.
        if not any("{{steps." + str(s.get("id")) + ".id}}" in prompt for _, s in earlier):
            named = ", ".join(f"`{s.get('id')}`" for _, s in earlier)
            problems.append(
                f"{name} step `{sid}` reads diaries with `{OWNED_APPOINTMENTS_QUERY}` and its "
                f"prompt never names the resolved customer ({{{{steps.<{named}>.id}}}}): the id "
                f"it passes has to come from somewhere, and with the resolver unmentioned that "
                f"somewhere is the model. Closing the lookup without handing over its answer does "
                f"not secure this step, it breaks it"
            )
    return problems


# ── «a customer, and only now» ────────────────────────────────────────────────────────────────
#
# The event these templates wait on is the CORE's (`crates/server/src/inbound_poll.rs`), and the
# poller asks the SaaS for `?direction=all&source=all`: everything the number ever saw comes
# through it. Since hub#1621 the payload says which is which — `direction` (who spoke), `source`
# (live traffic or the backlog WhatsApp hands over the day the number is connected) and `contact`
# (whose conversation it is). A trigger that does not ask answers all three, and two of them are
# not customers writing now:
#
# * the OWNER'S OWN REPLY, sent from the WhatsApp Business app on her phone, arrives here as an
#   `outbound` message. The automation reads it as a new customer message and answers the salon's
#   own number with «we will confirm your appointment as soon as we open»;
# * the 180-day BACKLOG arrives in one burst at connection time, so people who wrote in March get
#   a confirmation today for something that is over.
#
# 🔴 And the shape of the ANSWER matters as much as the shape of the question: a core below this
# module's declared floor (`compatibility.min_erplora_version`, whatsapp_inbox#62) predates
# hub#1621 and serves NONE of the three fields. In the kernel a missing path resolves to `Null`
# (`resolve_path` → `matches` in `crates/runtime/src/flows/def.rs`), and `json_eq(Null, x)` is
# `false` — so `{"event.direction": {"eq": "inbound"}}` turns the whole automation OFF on every
# hub at the floor, without an error, a log line or a run. The rule below therefore judges the
# filter by what it DOES to four real messages rather than by the operator it is written with,
# and one of the four is the message a floor-level core serves.
class _UnjudgeableFilter(Exception):
    """An operator this battery has no faithful copy of — refused out loud, never guessed."""


def _resolve(path, scope):
    """`resolve_path` in `crates/runtime/src/flows/def.rs`: any missing segment is `null`."""
    cursor = scope
    for segment in path.split("."):
        if not isinstance(cursor, dict) or segment not in cursor:
            return None
        cursor = cursor[segment]
    return cursor


def _json_eq(actual, expected):
    """`json_eq`: `null` equals nothing except `null` — the whole reason `eq` is a trap here."""
    if actual is None or expected is None:
        return actual is None and expected is None
    return actual == expected


def _clause_matches(op, actual, expected):
    """One operator of `eval()`. Anything this battery cannot copy faithfully is REFUSED."""
    if op == "eq":
        return _json_eq(actual, expected)
    if op == "neq":
        return not _json_eq(actual, expected)
    if op == "in":
        return isinstance(expected, list) and any(_json_eq(actual, i) for i in expected)
    if op == "exists":
        return (actual is not None) == (expected if isinstance(expected, bool) else True)
    raise _UnjudgeableFilter(op)


def _filter_matches(condition, scope):
    """`Condition::matches`: every clause of every path, in AND."""
    return all(
        _clause_matches(op, _resolve(path, scope), expected)
        for path, ops in (condition or {}).items()
        for op, expected in (ops or {}).items()
    )


CUSTOMER_NUMBER = "34600111222"
SALON_NUMBER = "34999888777"

# The four kinds of message one connected number hands this trigger, and whether the automation is
# supposed to wake up for it. `(label, event payload, should the filter let it through, why)`.
MESSAGE_KINDS = (
    (
        "a customer writing now",
        {
            "text": "hola, quiero cita mañana",
            "from": CUSTOMER_NUMBER,
            "contact": CUSTOMER_NUMBER,
            "direction": "inbound",
            "source": "live",
        },
        True,
        "it is the only thing this automation exists for",
    ),
    (
        "the owner's own reply, echoed back from her phone",
        {
            "text": "te confirmo a las 10:30",
            "from": SALON_NUMBER,
            "contact": CUSTOMER_NUMBER,
            "direction": "outbound",
            "source": "live",
        },
        False,
        "the salon is answered by its own automation, on its own number (whatsapp_inbox#66 is "
        "what puts the echo in the inbox; letting it TRIGGER is this one)",
    ),
    (
        "a message from the 180-day backlog",
        {
            "text": "hola, quiero cita mañana",
            "from": CUSTOMER_NUMBER,
            "contact": CUSTOMER_NUMBER,
            "direction": "inbound",
            "source": "history",
        },
        False,
        "everyone who wrote in the last six months is answered at once, today, about something "
        "that is over",
    ),
    (
        "the same customer, on a core at this module's declared floor",
        {"text": "hola, quiero cita mañana", "from": CUSTOMER_NUMBER},
        True,
        "a core below hub#1621 serves neither `direction` nor `source`, and in the kernel an "
        "absent path is `null`: a filter written with `eq`/`in`/`exists` matches NOTHING there, "
        "so the salon gets no automation at all and no error either",
    ),
)

# The fifth thing that arrives on this same event, and the one the four above cannot describe: the
# customer TAPPING a row of a list this automation sent her (whatsapp_inbox#101). Meta delivers a
# tap with NO text at all — the id and the label travel in `interactive.list_reply` — and the core
# hands the flow `reply_id`/`reply_title` filled and `text` EMPTY (hub#1633).
#
# It is kept OUT of `MESSAGE_KINDS` on purpose. Those four say who the automation is for, and every
# family answers them the same way. A tap only means something to a family that offered something
# to tap, so the half that depends on the family — «somebody has to wake up for it» — is asserted
# in `tappable_option_problems`, where that is known. What is asserted here is the half that is
# true everywhere, and it is the worst failure this channel has: never wake up TWICE.
TAP_KIND = (
    "a customer tapping a row of the list this automation sent her",
    {
        "text": "",
        "reply_id": "2026-09-08T10:30|staff:12|service:3",
        "reply_title": "mañana 10:30 · Ana",
        "from": CUSTOMER_NUMBER,
        "contact": CUSTOMER_NUMBER,
        "direction": "inbound",
        "source": "live",
    },
    None,
    "whether this family should wake up for a tap is `tappable_option_problems`' question",
)

# And the SIXTH shape, the one that makes the tap trigger hard to write: a photo, a sticker or a
# voice note, sent with no caption. It arrives with `text` EMPTY — like a tap — and the only thing
# telling the two apart is `reply_id`, which the core serves **empty and never absent** (hub#1633,
# `inbound_poll.rs`: "a flow comparing `reply_id` against something should simply not match a
# photo"). So `exists` is TRUE for every message that ever arrives, and only `neq ""` says «she
# tapped». A tap trigger written with `exists` reads exactly right and wakes the booking recipe up
# for every picture a customer sends: a metered turn spent on an empty message, and an answer she
# never asked for. Like TAP_KIND this belongs to the family that offers rows, so it is asserted in
# `tappable_option_problems` where that is known.
MEDIA_KIND = (
    "a photo sent with no caption",
    {
        "text": "",
        "reply_id": "",
        "reply_title": "",
        "from": CUSTOMER_NUMBER,
        "contact": CUSTOMER_NUMBER,
        "direction": "inbound",
        "source": "live",
    },
)

WHATSAPP_EVENT = "hub.whatsapp.message_received"


def whatsapp_triggers(doc):
    """Every event trigger of this document that waits on the core's WhatsApp event."""
    return [
        t
        for t in doc.get("triggers", [])
        if t.get("kind") == "event" and t.get("event") == WHATSAPP_EVENT
    ]


def only_the_customer_problems(name, doc):
    """The automation wakes up for a customer writing NOW — and can address her back on every
    core this module says it runs on.

    whatsapp_inbox#90. Two halves of one harm, and they are one rule because they are one bug:
    answering the wrong person.

    **The question.** The filter is run against the four messages in `MESSAGE_KINDS`, with this
    battery's copy of the kernel's `eval`, and every disagreement is named. Judging behaviour
    rather than syntax is deliberate: `{"event.direction": {"eq": "inbound"}}` and
    `{"event.direction": {"neq": "outbound"}}` both read as «only what the customer sent», and
    only the second one is still true on a core at the floor.

    **The answer.** A `notify` step resolves its recipient through
    `whatsapp_inbox.conversations.list`, and the value it filters by comes from the trigger's own
    `input` map. Every key it spends therefore has to be one a floor-level core can fill: mapping
    the recipient to `event.contact` — the field that is RIGHT in an echo — hands the query a
    `null` on that core, and `recipient_of` then refuses with `recipient_ambiguous` (or picks the
    hub's only conversation by luck). With the echo filtered out at the trigger, `event.from` IS
    the customer, on every core; `event.contact` becomes the better address the day the floor
    rises above hub#1621, and this rule goes red until it does.
    """
    problems = []
    triggers = whatsapp_triggers(doc)
    if not triggers:
        # A document that waits on some other event is not this rule's business. Said here rather
        # than falling out of an empty loop: with the union reading below, «no trigger matched the
        # customer» and «this document has no WhatsApp trigger» are the same expression, and only
        # the first one is a defect.
        return problems
    filters = [t.get("filter") or {} for t in triggers]

    # **The UNION, never each trigger on its own** (whatsapp_inbox#101). A message wakes this
    # automation up if ANY of its triggers matches it, so asking each one separately asks the wrong
    # question the moment there is more than one: the trigger that waits for a TAP is SUPPOSED to
    # ignore a customer writing words, and a per-trigger reading calls that «the automation is deaf
    # to the only thing it exists for».
    for label, payload, wanted, why in (*MESSAGE_KINDS, TAP_KIND):
        matched = []
        for condition in filters:
            try:
                if _filter_matches(condition, {"event": payload}):
                    matched.append(condition)
            except _UnjudgeableFilter as e:
                problems.append(
                    f"{name} filters on `{e}`, an operator this battery has no faithful copy of, "
                    f"so it cannot say who this trigger wakes up for. Add it to "
                    f"`_clause_matches` from `eval()` in `crates/runtime/src/flows/def.rs` in the "
                    f"same commit"
                )
                return problems
        if wanted is not None and bool(matched) != wanted:
            problems.append(
                f"{name} {'ignores' if wanted else 'answers'} {label}: {why}. Its trigger filters "
                f"are {json.dumps(filters, sort_keys=True)}"
            )
        # 🔴 …and exactly once. Two triggers that both match ONE message are two runs of the same
        # document over it, and in this channel that is the worst thing that can happen: the same
        # customer is booked twice, from one message, and nothing anywhere reports it — both runs
        # succeeded. Disjointness has to be a property of the filters themselves, not of how the
        # core happens to fill a field, which is why it is measured here against the payloads
        # rather than reasoned about in a comment.
        if len(matched) > 1:
            problems.append(
                f"{name} wakes up {len(matched)} times for {label}: the filters "
                f"{json.dumps(matched, sort_keys=True)} all match that one message, so the hub "
                f"starts that many runs of this document over it — two runs of a booking recipe "
                f"is one customer with two appointments, and both runs end `done`"
            )

    for trigger in triggers:
        mapping = trigger.get("input") or {}
        floor_event = next(p for lab, p, _, _ in MESSAGE_KINDS if lab.endswith("declared floor"))
        for step in doc.get("steps", []):
            if step.get("kind") != "notify":
                continue
            for param, expr in ((step.get("to") or {}).get("params") or {}).items():
                if not isinstance(expr, str) or not expr.startswith("input."):
                    continue
                key = expr.split(".", 1)[1]
                if key not in mapping:
                    problems.append(
                        f"{name} step `{step.get('id')}` addresses its reply by `{expr}`, and the "
                        f"trigger's `input` never maps `{key}`: the query is handed a `null`, so "
                        f"the recipient is whatever single conversation the hub happens to hold — "
                        f"or `recipient_ambiguous` the moment there are two"
                    )
                elif _resolve(mapping[key], {"event": floor_event}) is None:
                    problems.append(
                        f"{name} step `{step.get('id')}` addresses its reply by `{expr}` → "
                        f"`{mapping[key]}`, which a core at this module's declared floor does not "
                        f"serve (hub#1621). There it resolves to `null` and the message goes to "
                        f"whoever the query happens to answer with. With the echo filtered out at "
                        f"the trigger, `event.from` is the customer on every core; move to "
                        f"`event.contact` when the floor rises past hub#1621 (whatsapp_inbox#86)"
                    )
    return problems



# ── «que la toque, no que la escriba» — whatsapp_inbox#101 ────────────────────────────────────
#
# The booking families offered the free slots as PROSE and asked the customer to type a whole
# sentence back («corte, mañana a las 10:30»). She answers «10:30», or «el segundo», and what
# arrives is a brand-new run that never saw the list. On WhatsApp the normal thing is to TAP.
#
# The kernel halves landed apart: `notify.interactive` carries Meta's own object (hub#1633), and an
# `ai` step DECLARES what its turn leaves behind, with `options` being exactly Meta's row shape
# (hub#1639). What this rule pins is the WIRING between them, because every way of getting it wrong
# is silent — the document parses, the grants match, the run ends `done`:
#
#   * rows pointed at a step that never declared them resolve to `null`, and `notify` puts the
#     resolved object in the outbox without looking again: the list leaves for Meta with no rows;
#   * a producing step that can PARK a proposal never reaches `flow_answer` — the kernel refuses the
#     proposal by name (`agent_runner.rs`, hub#1639) — so the declared fields never arrive at all;
#   * an EMPTY list is a valid `options` answer and not a valid Meta message, so an unguarded send
#     fails after the customer has already been answered;
#   * and a list nobody can answer — no trigger that wakes for a tap — is worse than no list at all:
#     she taps, and nothing happens, ever.
#
# The producing step also still owes the customer WORDS. Its `text` is what `silence_problems`
# makes the `notify` carry, and with `output` declared the turn ends on a tool call whose
# accompanying content a model may leave empty — an empty WhatsApp message where the confirmation
# used to be. The kernel says so in its own briefing; the prompt has to say it too, because the
# prompt is what the model reads last.
TAP_WORDS = {
    "en": "ALWAYS write your reply to the customer in the same turn in which you call",
    "es": "Escribe SIEMPRE tu respuesta para la clienta en el mismo turno en el que llamas a",
}

# The bookings whose recipes have to let the customer TAP what she was offered. A table and not
# «every family» on purpose: a row is earned by a booking whose customer picks from a list.
#
# A TABLE was out until whatsapp_inbox#108, and the reason given was that it «is chosen by party
# size and hour together». Looked up rather than assumed (8 references: OpenTable, TheFork, Toast,
# Lightspeed, Square, Odoo, SevenRooms, Eat App): nobody offers the two together. Party size is an
# INPUT to the availability search — Toast caps covers per reservation increment, Lightspeed caps
# the party size per booking, Odoo filters the slots by «Number of People» — so every one of them
# asks how many first and only then shows the times. Which is exactly what this recipe already
# did in words («answer with what is really free»), so the list it earns is a list of TIMES for a
# party size already known.
TAPPABLE_BOOKINGS = (
    "appointments.appointments.create",
    "reservations.reservations.create",
)


def _is_path(value):
    """`is_path` in `crates/runtime/src/flows/def.rs`: a bare mapping path, resolved with its TYPE
    intact — which is the only reason an array of rows can travel inside `interactive` at all."""
    if not isinstance(value, str):
        return False
    root = value.split(".")[0]
    return root in ("input", "steps", "event", "secret") and len(value) > len(root) + 1


def option_slots(interactive):
    """`(where, value)` for every `rows`/`buttons` slot of a Meta interactive object."""
    found = []

    def walk(node, where):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("rows", "buttons"):
                    found.append((f"{where}.{key}", value))
                else:
                    walk(value, f"{where}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{where}[{index}]")

    walk(interactive or {}, "interactive")
    return found


def tappable_option_problems(name, doc):
    """The customer TAPS the slot she was offered instead of typing it back.

    whatsapp_inbox#101. Four things are pinned, and each of them is a way the recipe fails without
    saying anything: where the rows come from, that the step producing them can actually finish,
    that an empty list is never sent, and that a tap wakes something up — exactly once, which is
    `only_the_customer_problems`' half of the same rule.
    """
    problems = []
    steps = doc.get("steps", [])
    by_id = {s.get("id"): s for s in steps}
    lang = name.split(".")[1] if len(name.split(".")) >= 3 else ""
    offers = [(i, s) for i, s in enumerate(steps) if s.get("kind") == "notify" and s.get("interactive")]

    for index, step in offers:
        sid = step.get("id")
        if step.get("template") or (step.get("vars") or {}):
            problems.append(
                f"{name} step `{sid}` sends `interactive` AND its own copy: a WhatsApp message has "
                f"one type, so the hub refuses the document at save time rather than choosing one "
                f"of the two. The words belong in `interactive.body.text`"
            )
        for where, value in option_slots(step.get("interactive")):
            if not isinstance(value, str):
                # A literal list of rows is a fixed menu — legitimate, and nothing to wire.
                continue
            if not _is_path(value):
                problems.append(
                    f"{name} step `{sid}` fills `{where}` with `{value}`, which is not a mapping "
                    f"path: `resolve` only keeps an ARRAY when the whole value is a bare path, so "
                    f"anything else reaches Meta as the text of it"
                )
                continue
            parts = value.split(".")
            if len(parts) != 3 or parts[0] != "steps":
                problems.append(
                    f"{name} step `{sid}` fills `{where}` with `{value}`: the rows of a list come "
                    f"from a field an `ai` step DECLARED (`steps.<step>.<field>`, hub#1639), and "
                    f"any other path resolves to something with no `id`/`title` in it"
                )
                continue
            _, source, field = parts
            producer = by_id.get(source)
            if producer is None or producer.get("kind") != "ai":
                problems.append(
                    f"{name} step `{sid}` takes its rows from `{value}` and `{source}` is not an "
                    f"`ai` step of this document: the path resolves to `null` and the list is sent "
                    f"to Meta with no rows"
                )
                continue
            declared = (producer.get("output") or {}).get(field)
            if not isinstance(declared, dict) or declared.get("type") != "options":
                problems.append(
                    f"{name} step `{source}` never declares `output.{field}` as `options`, and "
                    f"step `{sid}` sends it as the rows of a list. Undeclared, the turn publishes "
                    f"`{{text, tool_calls}}` and nothing else: `{value}` is `null`, `notify` does "
                    f"not look again, and the send leaves with `rows: null`"
                )
                continue
            sentence = TAP_WORDS.get(lang)
            if sentence is None:
                problems.append(
                    f"{name} step `{source}` hands data back and this battery has no wording for "
                    f"language `{lang}`: add the translation to `TAP_WORDS` in the same commit"
                )
            elif sentence not in prompt_of(producer):
                problems.append(
                    f"{name} step `{source}` declares `output` and its prompt no longer says "
                    f"«{sentence}…»: a turn that ends on a tool call may carry no words with it, "
                    f"and `{sid}` would send the customer an empty message where her confirmation "
                    f"used to be"
                )
            guards = [
                s
                for s in steps[:index]
                if s.get("kind") == "condition"
                and (s.get("when") or {}).get(value, {}).get("neq") == []
            ]
            if not guards:
                problems.append(
                    f"{name} sends `{value}` as rows with no `condition` before step `{sid}` "
                    f"refusing the EMPTY list (`{{\"{value}\": {{\"neq\": []}}}}`). An empty list "
                    f"is a perfectly good answer — the turn booked, or answered a question — and "
                    f"is not a message Meta accepts, so the send fails AFTER she was answered. "
                    f"`exists` cannot stand in for it: `[]` is not null"
                )

    booking_steps = [
        s
        for s in steps
        if s.get("kind") == "ai"
        and any(b in ((s.get("tools") or {}).get("commands") or []) for b in TAPPABLE_BOOKINGS)
    ]
    # …and a recipe that BOOKS has to offer them, in either family. The attended one was out of
    # this rule until whatsapp_inbox#109, and the reason was real but narrower than it looked: the
    # step that proposes the appointment can never declare `output` (the kernel refuses a proposal
    # from a step that owes data, so the booking would become impossible), and the step that could
    # publish them saw only the proposal's PROSE, which carries no ids by design. What that argues
    # is WHICH step publishes them — the one that writes the message, holding the reads itself —
    # not that the customer who is being reviewed deserves the worse experience. She was the one
    # left typing «corte, mañana a las 10:30» at the salon that chose to be careful.
    if booking_steps and not offers:
        problems.append(
            f"{name} books with {', '.join(TAPPABLE_BOOKINGS)} and never offers the customer "
            f"anything to TAP: the free slots go out as prose and she has to type «corte, mañana a "
            f"las 10:30» back, which is where the bookings are lost (whatsapp_inbox#101/#109)"
        )

    if offers:
        woken = [
            t
            for t in whatsapp_triggers(doc)
            if _filter_matches(t.get("filter") or {}, {"event": TAP_KIND[1]})
        ]
        if not woken:
            problems.append(
                f"{name} offers rows to tap and no trigger of it wakes up for a tap: Meta sends a "
                f"tap with NO text, so a filter asking for `event.text` `neq` `\"\"` throws it "
                f"away. She taps the slot she was offered and nothing happens, with no error "
                f"anywhere — add a trigger on `event.reply_id`, disjoint from the one that waits "
                f"for words"
            )
        for trigger in woken:
            if "reply_id" not in (trigger.get("input") or {}):
                problems.append(
                    f"{name} wakes up for a tap and its `input` never maps `reply_id`: the run "
                    f"knows somebody tapped and not WHICH row, which is the ambiguity this whole "
                    f"change exists to remove"
                )
            # …and it has to tell a tap from a PHOTO, which arrives with `text` empty just the
            # same. The core serves `reply_id` empty and never ABSENT, so `exists` — the way of
            # writing this that reads right — is true for every message there is.
            if _filter_matches(trigger.get("filter") or {}, {"event": MEDIA_KIND[1]}):
                problems.append(
                    f"{name} wakes up for {MEDIA_KIND[0]} as well as for a tap: its filter "
                    f"{json.dumps(trigger.get('filter') or {}, sort_keys=True)} cannot tell them "
                    f"apart, because the core serves `reply_id` EMPTY and never absent "
                    f"(hub#1633), so anything but `neq \"\"` on it is true for a picture too. She "
                    f"sends one and this booking recipe runs over a message with no words in it — "
                    f"a metered turn, and an answer she never asked for"
                )
    return problems


def parking_producer_problems(name, doc, commands_def, read_perms):
    """A step that owes DATA has to be able to FINISH — judged by what its commands DO.

    It is asked of every `ai` step that declares `output`, and not only of the one whose rows a
    list sends. The two are the same dead end seen from two sides: a step that can neither park
    its write nor run it books nothing, and the list going out with `rows: null` is just the
    loudest way that shows. `writing_ai_steps` steps aside for exactly these steps — declaring
    `output` is what takes them out of it — so if this rule looked only at the published ones,
    nothing at all would judge the rest.

    The kernel's refusal is not «a step with `output` and commands»: it is a step that declares
    `output` and PROPOSES A WRITE (`agent_runner.rs`, hub#1639). A proposal ends the turn, so
    `flow_answer` is never called and the declared fields never arrive — approving it hours later
    publishes `{text, tool_calls}` and the names simply ABSENT, `rows` leaves for Meta as `null`.

    So the question is per COMMAND, not per step, and it is the same one hub#1595 answered for the
    approval tray: a command that only ANSWERS runs in the turn whatever the policy says and can
    never park. Reading it as «has commands» is stricter than the kernel by exactly the shape the
    attended family needs (whatsapp_inbox#109): there the step that books can never publish the
    slots, so the step that WRITES THE MESSAGE looks them up — `manual`, and with nothing but reads
    in its hands, it always reaches `flow_answer`.

    Manifest-aware, so it lives in the layer that skips OUT LOUD with no modules next door: without
    them nothing here can tell a read from a write, and guessing in either direction is worse than
    saying so.
    """
    problems = []
    # Which step publishes the rows of a list, and under which name — for the sentence, and only
    # for it. The question below is asked of EVERY step that owes data, whether or not a `notify`
    # reads it: judging only the published ones left the same dead end unguarded one step away —
    # a step whose write can neither park nor run, so the booking simply never happens.
    published = {}
    for step in doc.get("steps", []):
        if step.get("kind") != "notify" or not step.get("interactive"):
            continue
        for _, value in option_slots(step.get("interactive")):
            if not isinstance(value, str) or not _is_path(value):
                continue
            parts = value.split(".")
            if len(parts) != 3 or parts[0] != "steps":
                continue
            published.setdefault(parts[1], set()).add(parts[2])

    for step in doc.get("steps", []):
        if step.get("kind") != "ai" or not step.get("output"):
            continue
        if (step.get("policy") or "manual") == "auto":
            continue  # `auto` runs its writes in the turn: there is no proposal to park
        writes = sorted(
            cname
            for cname in ((step.get("tools") or {}).get("commands") or [])
            if cname in commands_def
            and not command_only_answers(commands_def[cname][1], read_perms.get(cname))
        )
        if not writes:
            continue
        step_id = step.get("id")
        fields = sorted(published.get(step_id) or step.get("output"))
        consequence = (
            "so the rows would leave for Meta as `null`"
            if step_id in published
            else "so that write can never happen at all — the model is handed a tool every call "
            "of which comes back refused, and nobody is told"
        )
        problems.append(
            f"{name} step `{step_id}` declares "
            f"{', '.join(f'`output.{f}`' for f in fields)} and can PARK a "
            f"proposal: under `policy: {step.get('policy') or 'manual'}` it may propose "
            f"{', '.join(f'`{w}`' for w in writes)}, which WRITES. The kernel refuses a "
            f"proposal from a step that owes data, by name, because a proposal ends the "
            f"turn and `flow_answer` would never be called — {consequence}. The step that owes "
            f"the data has to be one that can finish: reads only, or `policy: auto`"
        )
    return problems


# The keys the kernel accepts on each step kind — a copy of the `allowed` table in
# `hub/crates/runtime/src/flows/def.rs` (`parse_step`). The kernel refuses the WHOLE document for
# one key it does not know (`flow.invalid_definition`, «unknown key»), and the refusal only happens
# when the owner ACTIVATES the recipe: offering it reads the file as JSON and nothing more
# (`template_invalid_document`). So a template with a stray key is shown on the card, looks fine
# in review, and fails the one time it matters — whatsapp_inbox#171: `remember_the_customer`
# shipped with `payload` (the GRANT's word) where a `command` step takes `params`, and neither
# WhatsApp recipe could be switched on.
KERNEL_STEP_KEYS = {
    "command": {"id", "kind", "command", "params", "on_error", "run_if"},
    "query": {"id", "kind", "query", "params", "result", "limit", "options", "on_error", "run_if"},
    "condition": {"id", "kind", "when"},
    "delay": {
        "id", "kind", "seconds", "until", "offset_seconds", "max_wait", "past_due_policy",
        "cancel_on", "reschedule_on", "on_error", "run_if",
    },
    "http": {"id", "kind", "method", "url", "headers", "body", "timeout", "on_error", "run_if"},
    "ai": {
        "id", "kind", "prompt", "tools", "policy", "max_iters", "on_expire", "on_reject",
        "on_error", "output", "run_if",
    },
    "notify": {"id", "kind", "channel", "to", "template", "vars", "interactive", "on_error", "run_if"},
    "approval": {
        "id", "kind", "title", "summary", "assignee", "expires_in", "on_expire", "on_reject", "run_if",
    },
}


def unknown_step_key_problems(name, doc):
    """Every step carries only the keys the kernel accepts for its kind — whatsapp_inbox#171."""
    problems = []
    for step in doc.get("steps", []):
        kind = step.get("kind")
        allowed = KERNEL_STEP_KEYS.get(kind)
        if allowed is None:
            problems.append(
                f"{name} step `{step.get('id')}` has kind {kind!r}, which the kernel does not "
                f"know: activating the recipe is refused with `flow.invalid_definition`"
            )
            continue
        for key in sorted(set(step) - allowed):
            hint = " (a `command` step takes its payload in `params`)" if (
                kind == "command" and key == "payload"
            ) else ""
            problems.append(
                f"{name} step `{step.get('id')}` (`{kind}`) carries `{key}`, a key the kernel "
                f"does not accept{hint}: the card offers the recipe, and activating it is "
                f"refused whole with `flow.invalid_definition` — nobody gets an answer"
            )
    return problems


DOCUMENT_RULES = (
    floor_read_column_problems,
    home_country_match_problems,
    unfloored_read_problems,
    family_trigger_problems,
    confirmation_notice_problems,
    policy_problems,
    identified_cancellation_problems,
    identity_field_problems,
    floor_field_problems,
    floor_trigger_problems,
    silence_problems,
    mute_refusal_problems,
    unanswered_ending_problems,
    assistant_failure_problems,
    assistant_silence_problems,
    undeclared_tool_problems,
    unordered_tool_problems,
    budget_problems,
    enum_value_problems,
    unattended_problems,
    hour_choice_problems,
    birth_status_problems,
    birth_status_reading_problems,
    shipped_recipe_problems,
    unattended_ledger_problems,
    unowned_table_problems,
    moving_problems,
    own_customer_only_problems,
    unpinned_command_problems,
    unpinned_query_problems,
    missing_instruction_problems,
    only_the_customer_problems,
    tappable_option_problems,
    parking_producer_problems,
    unknown_step_key_problems,
)

# …and the registry itself is guarded, because it is the next place the same hole moves to. The
# ledger only demands the rules DOCUMENT_RULES names, so deleting a name from that tuple left the
# rule running, its cases passing and nothing requiring it to ever meet a real template again
# (whatsapp_inbox#61, mutant P4). Every rule `self_check()` proves has to be one `main()` is
# REQUIRED to apply, and that is asserted rather than assumed.
SELF_CHECKED_RULES = (
    floor_read_column_problems,
    home_country_match_problems,
    unfloored_read_problems,
    family_trigger_problems,
    confirmation_notice_problems,
    policy_problems,
    identified_cancellation_problems,
    identity_field_problems,
    floor_field_problems,
    floor_trigger_problems,
    silence_problems,
    mute_refusal_problems,
    unanswered_ending_problems,
    assistant_failure_problems,
    assistant_silence_problems,
    undeclared_tool_problems,
    unordered_tool_problems,
    budget_problems,
    enum_value_problems,
    unattended_problems,
    hour_choice_problems,
    birth_status_problems,
    birth_status_reading_problems,
    shipped_recipe_problems,
    unattended_ledger_problems,
    unowned_table_problems,
    moving_problems,
    own_customer_only_problems,
    unpinned_command_problems,
    unpinned_query_problems,
    missing_instruction_problems,
    only_the_customer_problems,
    tappable_option_problems,
    parking_producer_problems,
    unknown_step_key_problems,
)


def addressed_queries(doc):
    """`(step id, query id, sorted param names, where)` for every step that parameterises a query."""
    out = []
    for step in doc.get("steps", []):
        if step.get("kind") == "notify":
            to = step.get("to") or {}
            if isinstance(to.get("query"), str):
                out.append(
                    (
                        step.get("id"),
                        to["query"],
                        sorted(to.get("params") or {}),
                        "to.params",
                    )
                )
        elif step.get("kind") == "query" and isinstance(step.get("query"), str):
            out.append(
                (
                    step.get("id"),
                    step["query"],
                    sorted(step.get("params") or {}),
                    "params",
                )
            )
    return out


# The prose that lives INSIDE `interactive` and `output`: the two keys that are words AND
# machinery at once, so a translation may change part of them and no more (module-toolkit#209).
# The list is the toolkit's, on purpose. The same document is judged by both doors, and a battery
# that allowed what `erplora validate` refuses would only teach the author to ignore one of them.
# `*` is any key (the field names of `output` are the author's), `[]` any item of a LIST, and of a
# list only, so `rows` given as a mapping path stays the machinery it is.
PROSE_INSIDE = (
    "interactive.header.text",
    "interactive.body.text",
    "interactive.footer.text",
    "interactive.action.button",
    "interactive.action.sections[].title",
    "interactive.action.sections[].rows[].title",
    "interactive.action.sections[].rows[].description",
    "interactive.action.buttons[].reply.title",
    "output.*.describe",
)

# What a masked leaf reads as. A string no document carries and, being a string, it cannot be
# confused with a missing key: an absent `body.text` is not the same shape as a translated one.
PROSE = " prose"


def without_prose(value, paths):
    """`value` with the words the `paths` name masked out, so two languages that differ only in
    words compare equal. A path that does not fit what it lands on masks NOTHING: the value goes
    through untouched and is compared as machinery."""
    if any(not p for p in paths):
        return PROSE
    if isinstance(value, list):
        inside = [p[1:] for p in paths if p and p[0] == "[]"]
        return [without_prose(v, inside) for v in value] if inside else value
    if not isinstance(value, dict):
        return value
    out = {}
    for key, inner in value.items():
        inside = [p[1:] for p in paths if p and p[0] in (key, "*")]
        out[key] = without_prose(inner, inside) if inside else inner
    return out


def segments(path):
    """The path without its root key, with every `[]` as a step of its own."""
    out = []
    for part in path.split("."):
        if part.endswith("[]"):
            out.extend([part[:-2], "[]"])
        else:
            out.append(part)
    return out[1:]


def machinery_of(step, key):
    """What a translation must not change inside a MIXED key: everything except its prose."""
    if key not in step:
        return None
    return without_prose(
        step[key], [segments(p) for p in PROSE_INSIDE if p.split(".")[0] == key]
    )


def structural_shape(doc):
    """Everything about a document EXCEPT the human text — what a translation must not change."""
    return {
        "schema_version": doc.get("schema_version"),
        "triggers": [{k: v for k, v in t.items()} for t in doc.get("triggers", [])],
        "steps": [
            {
                "id": s.get("id"),
                "kind": s.get("kind"),
                "channel": s.get("channel"),
                "to": s.get("to"),
                "template": s.get("template"),
                "vars": sorted(s.get("vars", {})),  # the KEYS, never the copy
                "tools": s.get("tools"),
                "policy": s.get("policy"),
                "max_iters": s.get("max_iters"),
                # Machinery, not words: a Spanish document that dropped `on_reject` would cancel
                # its run at the rejection while the English one carried on, and the guard read
                # only the keys it was told about, so it saw two identical automations
                # (whatsapp_inbox#67).
                "on_reject": s.get("on_reject"),
                "on_expire": s.get("on_expire"),
                "on_error": s.get("on_error"),
                "command": s.get("command"),
                # The machinery of a `kind: query` step (hub#954), which was missing here until
                # whatsapp_inbox#125 — and it matters now because that family is made almost
                # entirely of reads: with these four left out, the Spanish document could point
                # its read at another query, key it on another field, or ask for `count` instead
                # of `first`, and this guard would call the two documents the same automation.
                "query": s.get("query"),
                "params": s.get("params"),
                "result": s.get("result"),
                "limit": s.get("limit"),
                "when": s.get("when"),
                "seconds": s.get("seconds"),
                # The two keys that carry words AND machinery (hub#1633/#1639), compared with the
                # words masked out: the Spanish list may say «Toca el hueco que te venga bien.»
                # while its `type`, its `rows` and the ids that come back stay identical. Left out
                # of this dict, a translation could point its rows at another step or declare
                # `slots` as `text`, and only the toolkit gate would ever notice (#109).
                "interactive": machinery_of(s, "interactive"),
                "output": machinery_of(s, "output"),
            }
            for s in doc.get("steps", [])
        ],
    }


def _offer(body="Tap one", button="See slots", section="Free slots", rows="steps.reply.slots",
           footer=None, kind="list"):
    """A `notify` that offers rows, with one screw loosened at a time."""
    interactive = {
        "type": kind,
        "body": {"text": body},
        "action": {"button": button, "sections": [{"title": section, "rows": rows}]},
    }
    if footer:
        interactive["footer"] = {"text": footer}
    return {"id": "offer", "kind": "notify", "channel": "whatsapp", "interactive": interactive}


def _publisher(describe="the free slots", field="slots", type_="options"):
    return {
        "id": "reply",
        "kind": "ai",
        "prompt": "write to her",
        "output": {field: {"type": type_, "describe": describe}},
    }


# `(label, English step, translated step, they are the SAME automation)`. The prose may differ and
# nothing else — the half of the parity check that reads the two MIXED keys (whatsapp_inbox#109).
SHAPE_CASES = [
    (
        "the words she reads are translated and it is the same automation",
        _offer(),
        _offer(body="Toca el que te venga bien", button="Ver huecos", section="Huecos libres"),
        True,
    ),
    (
        "…and so is what the MODEL reads about the field it publishes",
        _publisher(),
        _publisher(describe="los huecos libres"),
        True,
    ),
    (
        "🔴 the rows come from another step: the Spanish list would leave for Meta as `null`",
        _offer(),
        _offer(rows="steps.other.slots"),
        False,
    ),
    (
        "🔴 one of them is a button message and the other a list: two different messages",
        _offer(),
        _offer(kind="button"),
        False,
    ),
    (
        "🔴 a footer only one of them carries is a line only one customer reads",
        _offer(),
        _offer(footer="Te esperamos"),
        False,
    ),
    (
        "🔴 the field is declared as `text` in one and `options` in the other",
        _publisher(),
        _publisher(type_="text"),
        False,
    ),
    (
        "🔴 …or under another NAME, which later steps read by",
        _publisher(),
        _publisher(field="huecos"),
        False,
    ),
    (
        "a row written out in full may have its words translated, never its id",
        _offer(rows=[{"id": "2026-09-08T10:30|staff:12", "title": "Tuesday 10:30"}]),
        _offer(rows=[{"id": "2026-09-08T10:30|staff:12", "title": "Martes 10:30"}]),
        True,
    ),
    (
        "🔴 …and that id is what comes back when she taps: another one books another hour",
        _offer(rows=[{"id": "2026-09-08T10:30|staff:12", "title": "Tuesday 10:30"}]),
        _offer(rows=[{"id": "2026-09-08T12:00|staff:12", "title": "Martes 10:30"}]),
        False,
    ),
]


# ── layer 0: the battery checks its OWN rules before it judges anybody's file ─────────────────
#
# Everything else here is a rule about somebody else's document; this is the rule about the rules,
# and it exists because `policy_problems` is exactly the kind of check that passes by accident: it
# only ever runs over documents that are already correct, so a mutation that blinds it — dropping
# the `auto` branch, calling every command a read — leaves this battery green while the guard it is
# is gone. Every row below is a MUTANT: break the rule and one of them fails BY NAME.
_ANSWERS = {"permission": "appointments.view_schedule", "handler": "availability.wasm"}
_MODULE_READS = {"appointments.view_schedule", "appointments.view_appointment"}
_WRITES = {"permission": "appointments.add_appointment", "emit": ["appointments.created"]}

CLASSIFICATION_CASES = [
    (
        "a handler that writes nothing, paid for with a permission its own queries ask for",
        _ANSWERS,
        _MODULE_READS,
        True,
    ),
    ("`risk: normal` said out loud is still an answer", {**_ANSWERS, "ai": {"risk": "normal"}}, _MODULE_READS, True),
    (
        "`emit` is a write however the permission reads",
        {**_ANSWERS, "emit": ["appointments.availability.checked"]},
        _MODULE_READS,
        False,
    ),
    ("`sql` is a write", {**_ANSWERS, "sql": ["UPDATE appointments SET x = 1"]}, _MODULE_READS, False),
    ("`min_affected_rows` counts ROWS CHANGED", {**_ANSWERS, "min_affected_rows": 1}, _MODULE_READS, False),
    ("`expect_rows` counts ROWS CHANGED", {**_ANSWERS, "expect_rows": 1}, _MODULE_READS, False),
    (
        "a declared `risk` above normal beats every other signal",
        {**_ANSWERS, "ai": {"risk": "destructive"}},
        _MODULE_READS,
        False,
    ),
    (
        "a `view_`-looking permission NO query of the module asks for is a write",
        {"permission": "customers.view_customer"},
        _MODULE_READS,
        False,
    ),
    ("a write's own permission is not a read permission", _WRITES, _MODULE_READS, False),
    ("no permission at all is a write", {}, _MODULE_READS, False),
    ("a module whose queries were never read answers nothing", _ANSWERS, None, False),
]

_FIXTURE_COMMANDS = {
    "appointments.availability.slots": (None, _ANSWERS),
    "appointments.appointments.create": (None, _WRITES),
}
_FIXTURE_READS = {
    "appointments.availability.slots": _MODULE_READS,
    "appointments.appointments.create": _MODULE_READS,
}


def _ai_step(step_id, policy, commands, prompt="", on_reject=None, queries=(), max_iters=None):
    step = {
        "id": step_id,
        "kind": "ai",
        "policy": policy,
        "prompt": prompt,
        "tools": {"commands": list(commands)},
    }
    if queries:
        step["tools"]["queries"] = list(queries)
    if on_reject is not None:
        step["on_reject"] = on_reject
    if max_iters is not None:
        step["max_iters"] = max_iters
    return step


def _query_step(step_id, query=None, params=None):
    """The deterministic read (hub#954): the DOCUMENT maps the params, never the model."""
    step = {
        "id": step_id,
        "kind": "query",
        "query": RESOLVER_QUERY if query is None else query,
        "result": "first",
        "limit": 1,
    }
    if params is not None:
        step["params"] = dict(params)
    return step


def _relay_step(step_id, writer, prompt=""):
    """The step whatsapp_inbox#67 adds: it reads how the turn ended and writes what to send."""
    return {
        "id": step_id,
        "kind": "ai",
        "policy": "manual",
        "max_iters": 1,
        "prompt": (
            f"{prompt}Outcome: {{{{steps.{writer}.status}}}}. "
            f"Words: {{{{steps.{writer}.text}}}}"
        ),
    }


def _ending_relay(step_id, writer, names=("expired", "failed")):
    """A relay that reads how the turn ended AND names the endings it may read back.

    The shape whatsapp_inbox#70 needs: `_relay_step` already quotes `status`, which is what
    `mute_refusal_problems` asks for, and this adds the two words a status can now carry so the
    prompt cannot fall into its «nothing was refused» branch on one of them.
    """
    step = _relay_step(step_id, writer)
    step["prompt"] += " Endings: " + ", ".join(f"`{n}`" for n in names)
    return step


def _fixture_doc(*steps):
    return {"schema_version": 1, "triggers": [], "steps": list(steps)}


# The name a mutant document is judged UNDER: the family is what buys the unattended exception, so
# every row carries one. `(label, file name, document, problems expected)`.
#
# There is no attended sibling any more (whatsapp_inbox#124): one use gets ONE recipe, and the
# family that ships IS the one that runs with nobody watching, under the plain name. What the
# negative rows still need is real — a family `flows/` could grow that `UNATTENDED_FAMILIES` does
# not name — and that is what `UNNAMED_FAMILY` stands for. Keeping those rows is not nostalgia for
# the deleted recipe: it is what proves these rules key off the LEDGER and not off «every document
# in this repo», which is the difference between a rule and a coincidence. Their silence is only
# safe because `unattended_ledger_problems` refuses to let such a family ship at all, and that
# division of labour is deliberate: a rule that also policed the ledger would report the same hole
# twice and neither report would be the one to fix.
UNATTENDED = "appointment-from-whatsapp.en.flow.json"
UNNAMED_FAMILY = "order-from-whatsapp.en.flow.json"

def _sends(step_id, text):
    """A `notify` that SENDS what an earlier step wrote — the delivery, not a handoff of findings."""
    return {"id": step_id, "kind": "notify", "channel": "whatsapp", "template": "", "vars": {"text": text}}


POLICY_CASES = [
    (
        "a read inside a `manual` step is what hub#1595 made legal",
        UNNAMED_FAMILY,
        _fixture_doc(_ai_step("s", "manual", ["appointments.availability.slots"])),
        0,
    ),
    (
        "a write inside an `auto` step is still the dangerous direction",
        UNNAMED_FAMILY,
        _fixture_doc(_ai_step("s", "auto", ["appointments.appointments.create"])),
        1,
    ),
    (
        "the SAME write, in the family whose name declares that it runs with nobody watching, is "
        "what that family exists for (whatsapp_inbox#58) — the exception is the file name, and it "
        "is the only thing that changes between this row and the one above",
        UNATTENDED,
        _fixture_doc(_ai_step("s", "auto", ["appointments.appointments.create"])),
        0,
    ),
    (
        "and the exception is scoped to that family and no other: a name that merely CONTAINS the "
        "word buys nothing, or the guard would be one rename away from being off everywhere",
        "appointment-from-whatsapp-draft.en.flow.json",
        _fixture_doc(_ai_step("s", "auto", ["appointments.appointments.create"])),
        1,
    ),
    (
        "a write inside a `manual` step is the default, and the point of it",
        UNNAMED_FAMILY,
        _fixture_doc(_ai_step("s", "manual", ["appointments.appointments.create"])),
        0,
    ),
    (
        "a read inside an `auto` step is fine",
        UNNAMED_FAMILY,
        _fixture_doc(_ai_step("s", "auto", ["appointments.availability.slots"])),
        0,
    ),
    (
        "the step that WRITES the message, whose words a `notify` SENDS, is not the split: nobody "
        "reads its prose to work from it — it goes to the customer, which is what that step is "
        "for. It is also the only step of the attended family that can look the slots up and "
        "publish them, because the one that books can never declare `output` (whatsapp_inbox#109)",
        UNNAMED_FAMILY,
        _fixture_doc(
            _ai_step("reply", "manual", ["appointments.availability.slots"]),
            _sends("send", "{{steps.reply.text}}"),
        ),
        0,
    ),
    (
        "…and the split is still the split when the reader feeds a step that ACTS, even if a "
        "notify quotes it too: one reader, two mouths, and the ids still travel as words",
        UNNAMED_FAMILY,
        _fixture_doc(
            _ai_step("look", "auto", ["appointments.availability.slots"]),
            _ai_step("act", "manual", ["appointments.appointments.create"], "{{steps.look.text}}"),
            _sends("send", "{{steps.look.text}}"),
        ),
        1,
    ),
    (
        "a step that only asks, feeding a step that acts, is the split whatsapp_inbox#55 removed",
        UNNAMED_FAMILY,
        _fixture_doc(
            _ai_step("look", "auto", ["appointments.availability.slots"]),
            _ai_step("act", "manual", ["appointments.appointments.create"], "{{steps.look.text}}"),
        ),
        1,
    ),
    (
        "…and it is still the split in the unattended family: running with nobody watching is a "
        "reason to skip the approval tray, never a reason to pay for two AI turns",
        UNATTENDED,
        _fixture_doc(
            _ai_step("look", "auto", ["appointments.availability.slots"]),
            _ai_step("act", "auto", ["appointments.appointments.create"], "{{steps.look.text}}"),
        ),
        1,
    ),
    (
        "the same split quoted with spaces inside the braces — `{{ steps.look.text }}` — is still "
        "the split: the hub trims the path before resolving it (`render_template`), so the "
        "guard has to read it the way the hub does",
        UNNAMED_FAMILY,
        _fixture_doc(
            _ai_step("look", "auto", ["appointments.availability.slots"]),
            _ai_step("act", "manual", ["appointments.appointments.create"], "{{ steps.look.text }}"),
        ),
        1,
    ),
    (
        "a step that only asks and that nobody quotes is not the split",
        UNNAMED_FAMILY,
        _fixture_doc(
            _ai_step("look", "auto", ["appointments.availability.slots"]),
            _ai_step("act", "manual", ["appointments.appointments.create"]),
        ),
        0,
    ),
    (
        "asking and proposing in ONE step is the shape this repo now ships",
        UNNAMED_FAMILY,
        _fixture_doc(
            _ai_step(
                "act",
                "manual",
                ["appointments.availability.slots", "appointments.appointments.create"],
            )
        ),
        0,
    ),
]


def _notify_step(step_id="tell", text="done"):
    return {
        "id": step_id,
        "kind": "notify",
        "channel": "whatsapp",
        "to": {"query": "whatsapp_inbox.conversations.list", "params": {"f_wa_contact_id": "input.from"}, "field": "contact_phone"},
        "template": "",
        "vars": {"text": text},
    }


def _approval_step(step_id="ask"):
    return {"id": step_id, "kind": "approval", "prompt": "Book it?"}


UNATTENDED_CASES = [
    (
        "the shape the unattended family ships: the step that books runs in the turn, and the "
        "customer is told",
        UNATTENDED,
        _fixture_doc(
            _ai_step("book", "auto", ["appointments.appointments.create"]),
            _notify_step(),
        ),
        0,
    ),
    (
        "the regression this rule exists for (whatsapp_inbox#58): the booking step put back on "
        "`manual`. Nothing refuses it — the document saves, the trigger arms, the customer is "
        "answered — and the write waits in `_flow_approvals` for a person this business does not "
        "have",
        UNATTENDED,
        _fixture_doc(
            _ai_step("book", "manual", ["appointments.appointments.create"]),
            _notify_step(),
        ),
        1,
    ),
    (
        "one of two steps back on `manual` is the same lie: the customer record is created by a "
        "person or not at all, and the run never reaches the booking",
        UNATTENDED,
        _fixture_doc(
            _ai_step("know", "manual", ["customers.create"]),
            _ai_step("book", "auto", ["appointments.appointments.create"]),
            _notify_step(),
        ),
        1,
    ),
    (
        "an `approval` step is the kernel's explicit pause (hub#950): it stops the run dead, "
        "which is exactly what this family promises it does not do",
        UNATTENDED,
        _fixture_doc(
            _ai_step("book", "auto", ["appointments.appointments.create"]),
            _approval_step(),
            _notify_step(),
        ),
        1,
    ),
    (
        "a step that only READS is not held to `auto`: since hub#1595 an operation that only "
        "answers runs in the turn under either policy, so its `policy` decides nothing",
        UNATTENDED,
        _fixture_doc(
            _ai_step("look", "manual", []),
            _ai_step("book", "auto", ["appointments.appointments.create"]),
            _notify_step(),
        ),
        0,
    ),
    (
        "and the rule is silent on every other family: parking at a person is what the attended "
        "sibling is FOR, and an `approval` step there is a feature",
        UNNAMED_FAMILY,
        _fixture_doc(
            _ai_step("book", "manual", ["appointments.appointments.create"]),
            _approval_step(),
            _notify_step(),
        ),
        0,
    ),
]


UNATTENDED_ES = "appointment-from-whatsapp.es.flow.json"
# The table family (whatsapp_inbox#60). A restaurant runs the same automation against
# `reservations`, so it inherits the same rules — including this one, under its own wording — and
# since whatsapp_inbox#124 it is ONE family, like the chair.
TABLE_UNATTENDED = "reservation-from-whatsapp.en.flow.json"
TABLE_UNATTENDED_ES = "reservation-from-whatsapp.es.flow.json"
TABLE_UNNAMED_FAMILY = "order-from-whatsapp.en.flow.json"

HOUR_CASES = [
    (
        "the shape the unattended family ships: the step that can book carries the rule, in its "
        "own language",
        UNATTENDED,
        _fixture_doc(_ai_step("book", "auto", [BOOKING_COMMAND], f"Book it. {HOUR_RULE['en']} Go.")),
        0,
    ),
    (
        "the regression this rule exists for (reviewer mutant N2 on whatsapp_inbox#58): the rule "
        "reworded away, and a bot with nobody behind it books people into hours they never asked "
        "for — the document saves, the trigger arms, and nothing anywhere says so",
        UNATTENDED,
        _fixture_doc(_ai_step("book", "auto", [BOOKING_COMMAND], "Book whatever fits best.")),
        1,
    ),
    (
        "the Spanish document carries the Spanish wording",
        UNATTENDED_ES,
        _fixture_doc(_ai_step("book", "auto", [BOOKING_COMMAND], f"Resérvala. {HOUR_RULE['es']}")),
        0,
    ),
    (
        "a translation that kept the English sentence dropped the rule for the reader it has: the "
        "model reads the prompt in the language it is written in, and so does the salon",
        UNATTENDED_ES,
        _fixture_doc(_ai_step("book", "auto", [BOOKING_COMMAND], f"Resérvala. {HOUR_RULE['en']}")),
        1,
    ),
    (
        "a step that cannot book owes no such promise: the customer-record step writes, but not "
        "into the diary",
        UNATTENDED,
        _fixture_doc(_ai_step("know", "auto", ["customers.create"], "Find or create them.")),
        0,
    ),
    (
        "silent on the attended family: there a person reads the proposal before it books",
        UNNAMED_FAMILY,
        _fixture_doc(_ai_step("book", "manual", [BOOKING_COMMAND], "Book whatever fits best.")),
        0,
    ),
    (
        "a language this battery has no wording for is a document it cannot vouch for — a third "
        "translation adds its sentence to HOUR_RULE in the same commit, or it does not ship",
        "appointment-from-whatsapp.fr.flow.json",
        _fixture_doc(_ai_step("book", "auto", [BOOKING_COMMAND], f"Réserve. {HOUR_RULE['en']}")),
        1,
    ),
    (
        "the shape the unattended TABLE family ships (whatsapp_inbox#60): booking a table is the "
        "same bet as booking a chair, so the step that can book carries its own wording of the "
        "rule",
        TABLE_UNATTENDED,
        _fixture_doc(
            _ai_step("book", "auto", [TABLE_BOOKING_COMMAND], f"Book it. {TABLE_RULE['en']} Go.")
        ),
        0,
    ),
    (
        "the SAME regression on the table family, and the reason this rule is a table and not one "
        "command: a bot that picks the hour — or the number of diners — with nobody in the "
        "restaurant seats four people at a table for two, and the document saves, the trigger arms "
        "and nothing anywhere says so",
        TABLE_UNATTENDED,
        _fixture_doc(
            _ai_step("book", "auto", [TABLE_BOOKING_COMMAND], "Book whatever fits best.")
        ),
        1,
    ),
    (
        "the Spanish table document carries the Spanish wording",
        TABLE_UNATTENDED_ES,
        _fixture_doc(
            _ai_step("book", "auto", [TABLE_BOOKING_COMMAND], f"Resérvala. {TABLE_RULE['es']}")
        ),
        0,
    ),
    (
        "a table translation that kept the English sentence dropped the rule for the reader it has",
        TABLE_UNATTENDED_ES,
        _fixture_doc(
            _ai_step("book", "auto", [TABLE_BOOKING_COMMAND], f"Resérvala. {TABLE_RULE['en']}")
        ),
        1,
    ),
    (
        "silent on the attended table family: there a person reads the proposal before it books",
        TABLE_UNNAMED_FAMILY,
        _fixture_doc(
            _ai_step("book", "manual", [TABLE_BOOKING_COMMAND], "Book whatever fits best.")
        ),
        0,
    ),
    (
        "the appointment wording is NOT the table wording: a table document that carries the "
        "chair sentence is a document whose rule never mentions how many people are coming",
        TABLE_UNATTENDED,
        _fixture_doc(
            _ai_step("book", "auto", [TABLE_BOOKING_COMMAND], f"Book it. {HOUR_RULE['en']}")
        ),
        1,
    ),
]


# `(label, file name, document, problems expected)` — same shape as HOUR_CASES, and judged under a
# file name for the same reason: the language of the document is in its name.
_MOVE_TOOLS = (BOOKING_COMMAND, CANCEL_COMMAND, MOVE_COMMAND)
_MOVE_QUERIES = (OWNED_APPOINTMENTS_QUERY,)

# `(label, file name, document, problems expected)` — the unit tests of `birth_status_problems`,
# the rule whatsapp_inbox#124 is about. Both halves of it are proved here: the deterministic READ
# that is the only thing in the run that knows how the booking will be born, and the two SENTENCES
# it leads to, per language.
_APPT_SETTINGS = BIRTH_STATUS_SOURCE[BOOKING_COMMAND]
_TABLE_SETTINGS = BIRTH_STATUS_SOURCE[TABLE_BOOKING_COMMAND]
_BIRTH_EN = BIRTH_STATUS_RULES[BOOKING_COMMAND]["en"]
_BIRTH_ES = BIRTH_STATUS_RULES[BOOKING_COMMAND]["es"]
_TABLE_BIRTH_EN = BIRTH_STATUS_RULES[TABLE_BOOKING_COMMAND]["en"]
_TABLE_BIRTH_ES = BIRTH_STATUS_RULES[TABLE_BOOKING_COMMAND]["es"]


def _books(prompt, query=_APPT_SETTINGS, command=BOOKING_COMMAND, step_id="book_appointment"):
    """A document that reads the setting and then books, which is the shape #124 leaves."""
    steps = [_ai_step(step_id, "auto", (command,), prompt)]
    if query is not None:
        steps.insert(0, _query_step("booking_policy", query))
    return _fixture_doc(*steps)


BIRTH_STATUS_CASES = [
    (
        "the shape whatsapp_inbox#124 ships: the document reads the setting that decides the birth "
        "status, and the prompt carries both endings that read leads to",
        UNATTENDED,
        _books(f"Book it. {_BIRTH_EN['pending']} {_BIRTH_EN['confirmed']}"),
        0,
    ),
    (
        "🔴 the red this issue IS, with `auto_confirm_online = 0`: the salon reviews, the "
        "appointment is born `pending`, and the only sentence the recipe knows says «booked». The "
        "customer is sent to a slot nobody has accepted, the document parses, the grants match and "
        "nothing anywhere says so",
        UNATTENDED,
        _books(f"Book it. {_BIRTH_EN['confirmed']}"),
        1,
    ),
    (
        "…and the mirror, which is the same bug wearing the other face: the salon that switched "
        "«confirm automatically» ON has its bookings in the diary already, and the customer is "
        "left waiting for a confirmation message that is never coming",
        UNATTENDED,
        _books(f"Book it. {_BIRTH_EN['pending']}"),
        1,
    ),
    (
        "neither ending: the prompt was rewritten and both sentences went with it",
        UNATTENDED,
        _books("Book whatever fits best and tell her."),
        2,
    ),
    (
        "🔴 the READ deleted, both sentences intact: this is the half that looks harmless, because "
        "the prompt still reads perfectly. Without it the model has nothing in the run that says "
        "which ending applies — `appointments.appointments.create` answers `{ok, operations, "
        "new_ids}` with no status in it — so it picks one, and half the businesses are told the "
        "opposite of what their diary holds",
        UNATTENDED,
        _books(f"Book it. {_BIRTH_EN['pending']} {_BIRTH_EN['confirmed']}", query=None),
        1,
    ),
    (
        "a read of SOMEBODY ELSE's settings is not the read: the restaurant's `auto_confirm` says "
        "nothing about how a chair is born",
        UNATTENDED,
        _books(f"Book it. {_BIRTH_EN['pending']} {_BIRTH_EN['confirmed']}", query=_TABLE_SETTINGS),
        1,
    ),
    (
        "the setting read by the MODEL instead of by the document is not the read either: "
        "`book_appointment` runs at `max_iters` 10 = `MAX_ITERS_CAP`, so a lookup the model has to "
        "remember is a lookup it will sometimes not do — and the run where it forgets is the run "
        "where the customer is told the wrong thing",
        UNATTENDED,
        _fixture_doc(
            _ai_step(
                "book_appointment",
                "auto",
                (BOOKING_COMMAND,),
                f"Book it. {_BIRTH_EN['pending']} {_BIRTH_EN['confirmed']}",
                queries=(_APPT_SETTINGS,),
            )
        ),
        1,
    ),
    (
        "the Spanish document carries the Spanish endings",
        UNATTENDED_ES,
        _books(f"Resérvala. {_BIRTH_ES['pending']} {_BIRTH_ES['confirmed']}"),
        0,
    ),
    (
        "a translation that kept the English sentences dropped both endings for the reader it has: "
        "the model reads the prompt in the language it is written in, and so does the salon",
        UNATTENDED_ES,
        _books(f"Resérvala. {_BIRTH_EN['pending']} {_BIRTH_EN['confirmed']}"),
        2,
    ),
    (
        "one ending translated and one left in English, which is how it really happens: a "
        "translator keeps the paragraph and drops the sentence at the end of it",
        UNATTENDED_ES,
        _books(f"Resérvala. {_BIRTH_ES['pending']} {_BIRTH_EN['confirmed']}"),
        1,
    ),
    (
        "a language this battery has no wording for is a document it cannot vouch for — a third "
        "translation adds its two sentences in the same commit, or it does not ship",
        "appointment-from-whatsapp.fr.flow.json",
        _books(f"Réserve. {_BIRTH_EN['pending']} {_BIRTH_EN['confirmed']}"),
        1,
    ),
    (
        "a step that cannot book owes no ending: the customer-record step writes, but not into the "
        "diary",
        UNATTENDED,
        _books("Find or create them.", command="customers.create", step_id="know_the_customer"),
        0,
    ),
    (
        "the table family owes the same two endings, under its own wording and its own setting "
        "(`reservations`' `auto_confirm` defaults to 0, so the ordinary restaurant REVIEWS)",
        TABLE_UNATTENDED,
        _books(
            f"Book it. {_TABLE_BIRTH_EN['pending']} {_TABLE_BIRTH_EN['confirmed']}",
            query=_TABLE_SETTINGS,
            command=TABLE_BOOKING_COMMAND,
            step_id="book_table",
        ),
        0,
    ),
    (
        "🔴 and the same red on the table side, which is the one that bites by default: with "
        "`auto_confirm` 0 the table is born pending for every restaurant that never touched the "
        "setting, and a recipe that only knows «booked» seats nobody",
        TABLE_UNATTENDED,
        _books(
            f"Book it. {_TABLE_BIRTH_EN['confirmed']}",
            query=_TABLE_SETTINGS,
            command=TABLE_BOOKING_COMMAND,
            step_id="book_table",
        ),
        1,
    ),
    (
        "the Spanish table document carries the Spanish endings",
        TABLE_UNATTENDED_ES,
        _books(
            f"Resérvala. {_TABLE_BIRTH_ES['pending']} {_TABLE_BIRTH_ES['confirmed']}",
            query=_TABLE_SETTINGS,
            command=TABLE_BOOKING_COMMAND,
            step_id="book_table",
        ),
        0,
    ),
    (
        "the appointment wording is NOT the table wording: a table document carrying the chair "
        "sentences tells a party of four about a salon",
        TABLE_UNATTENDED,
        _books(
            f"Book it. {_BIRTH_EN['pending']} {_BIRTH_EN['confirmed']}",
            query=_TABLE_SETTINGS,
            command=TABLE_BOOKING_COMMAND,
            step_id="book_table",
        ),
        2,
    ),
]

# `(label, file name, document, floors, problems expected)` — the unit tests of
# `birth_status_reading_problems`, the rule whatsapp_inbox#152 is about.
_TABLE_READ_EN = BIRTH_STATUS_READING[TABLE_BOOKING_COMMAND]["en"]
_TABLE_READ_ES = BIRTH_STATUS_READING[TABLE_BOOKING_COMMAND]["es"]
_TABLE_EMPTY_EN = BIRTH_STATUS_EMPTY[TABLE_BOOKING_COMMAND]["en"]
_TABLE_EMPTY_ES = BIRTH_STATUS_EMPTY[TABLE_BOOKING_COMMAND]["es"]
_APPT_READ_EN = BIRTH_STATUS_READING[BOOKING_COMMAND]["en"]
_APPT_EMPTY_EN = BIRTH_STATUS_EMPTY[BOOKING_COMMAND]["en"]
_BOOLEAN_FLOOR = {"reservations": BIRTH_STATUS_BOOLEAN_SINCE[TABLE_BOOKING_COMMAND][1]}
# What both table prompts said before whatsapp_inbox#152, word for word.
_RAW_TABLE_EN = (
    "it comes back raw: `1` means the table you just booked is already accepted, `0` means it is "
    "waiting for somebody at the restaurant to accept it. If it comes back EMPTY this restaurant "
    "has never saved its reservation settings, and Reservas treats that as OFF, so read it as `0`."
)
_RAW_TABLE_ES = (
    "viene crudo: `1` significa que la mesa que acabas de reservar ya está aceptada, `0` que está "
    "esperando a que alguien del restaurante la acepte. Si viene VACÍO, este restaurante no ha "
    "guardado nunca sus ajustes de reservas, y Reservas lo trata como APAGADO, así que léelo como `0`."
)


def _books_table(prompt):
    return _books(
        prompt, query=_TABLE_SETTINGS, command=TABLE_BOOKING_COMMAND, step_id="book_table"
    )


BIRTH_READING_CASES = [
    (
        "the shape whatsapp_inbox#152 ships: the table prompt reads the switch as `true`/`false`, "
        "an empty answer as `false`, and the family floors Reservas where it answers a boolean",
        TABLE_UNATTENDED,
        _books_table(f"Book it. {_TABLE_READ_EN} If empty, {_TABLE_EMPTY_EN}"),
        _BOOLEAN_FLOOR,
        0,
    ),
    (
        "🔴 the red this issue IS: the prompt still explains `1`/`0` over a read that answers "
        "`true`/`false` — the reading sentence is missing, the empty reading is missing, and the "
        "stale integer wording is there",
        TABLE_UNATTENDED,
        _books_table(f"Book it. {_RAW_TABLE_EN}"),
        _BOOLEAN_FLOOR,
        3,
    ),
    (
        "…and the Spanish twin, which said the same thing in Spanish",
        TABLE_UNATTENDED_ES,
        _books_table(f"Resérvala. {_RAW_TABLE_ES}"),
        _BOOLEAN_FLOOR,
        3,
    ),
    (
        "the Spanish table document with the Spanish boolean reading",
        TABLE_UNATTENDED_ES,
        _books_table(f"Resérvala. {_TABLE_READ_ES} Si viene vacío, {_TABLE_EMPTY_ES}"),
        _BOOLEAN_FLOOR,
        0,
    ),
    (
        "both wordings at once: the boolean sentences were added and the raw ones left behind, a "
        "prompt that contradicts itself",
        TABLE_UNATTENDED,
        _books_table(f"Book it. {_TABLE_READ_EN} {_TABLE_EMPTY_EN} {_RAW_TABLE_EN}"),
        _BOOLEAN_FLOOR,
        1,
    ),
    (
        "🔴 the right words over the wrong floor: a hub on Reservas 3.0.28 still answers `0`/`1`, "
        "and the hub offers the recipe there because `requires.json` says it may",
        TABLE_UNATTENDED,
        _books_table(f"Book it. {_TABLE_READ_EN} {_TABLE_EMPTY_EN}"),
        {"reservations": "3.0.28"},
        1,
    ),
    (
        "…and a family that declares no Reservas floor at all is offered everywhere",
        TABLE_UNATTENDED,
        _books_table(f"Book it. {_TABLE_READ_EN} {_TABLE_EMPTY_EN}"),
        {},
        1,
    ),
    (
        "the empty answer read as the SALON reads it: a restaurant with no settings reviews, so "
        "«read it as `true`» tells the customer of every such restaurant her table is booked",
        TABLE_UNATTENDED,
        _books_table(f"Book it. {_TABLE_READ_EN} {_APPT_EMPTY_EN}"),
        _BOOLEAN_FLOOR,
        1,
    ),
    (
        "the salon recipe already speaks `true`/`false`, and Citas owes no Reservas floor",
        UNATTENDED,
        _books(f"Book it. {_APPT_READ_EN} If empty, {_APPT_EMPTY_EN}"),
        {},
        0,
    ),
    (
        "a step that cannot book owes no reading",
        TABLE_UNATTENDED,
        _books("Find or create them.", command="customers.create", step_id="know_the_customer"),
        {},
        0,
    ),
]


# `(label, the families that really ship, problems expected)` — the unit tests of
# `unattended_ledger_problems`. It takes no document on purpose: what it judges is the agreement
# between a table in this file and a folder on disk, so both halves are handed in.
LEDGER_CASES = [
    (
        "table and `flows/` say the same thing, which is the healthy tree",
        set(UNATTENDED_FAMILIES),
        0,
    ),
    (
        "🔴 a family SHIPS and the table does not name it: every rule that asks «is anybody "
        "watching?» reads this table, so that recipe books with nobody watching while "
        "`unattended_problems` and `hour_choice_problems` stay silent over it — and "
        "`policy_problems` reports its writes as a defect instead. This is the shape "
        "whatsapp_inbox#124 creates the day somebody adds a third recipe",
        set(UNATTENDED_FAMILIES) | {"order-from-whatsapp"},
        1,
    ),
    (
        "🔴 and the mirror, which is the one a rename leaves behind: the table names a family and "
        "no document belongs to it. Every rule keyed off that row goes vacuously green, and the "
        "business the row was written for has nothing to install",
        set(UNATTENDED_FAMILIES) - {"reservation-from-whatsapp"},
        1,
    ),
    (
        "a rename done in `flows/` and not here is BOTH halves at once, and it is exactly what "
        "whatsapp_inbox#124 did: the old name orphaned, the new one unnamed",
        (set(UNATTENDED_FAMILIES) - {"appointment-from-whatsapp"})
        | {"appointment-from-whatsapp-unattended"},
        2,
    ),
    (
        "nothing ships: every row is a promise nothing keeps",
        set(),
        len(UNATTENDED_FAMILIES),
    ),
]


# One family per booking, which is what whatsapp_inbox#124 leaves: `booked` maps a family to every
# command its `ai` steps can call, and the rule wants exactly one name per booking — no more (the
# owner would have to guess) and no less (the business has nothing to install).
_CHAIR = {"appointment-from-whatsapp": {BOOKING_COMMAND}}
_TABLE = {"reservation-from-whatsapp": {TABLE_BOOKING_COMMAND}}
_CHAIR_PAIR = {
    "appointment-from-whatsapp": {BOOKING_COMMAND},
    "appointment-from-whatsapp-unattended": {BOOKING_COMMAND},
}
_TABLE_PAIR = {
    "reservation-from-whatsapp": {TABLE_BOOKING_COMMAND},
    "reservation-from-whatsapp-unattended": {TABLE_BOOKING_COMMAND},
}

RECIPE_CASES = [
    (
        "what this module ships after whatsapp_inbox#124: exactly ONE family for every booking "
        "the battery has a wording for",
        {**_CHAIR, **_TABLE},
        0,
    ),
    (
        "the red whatsapp_inbox#60 IS: the table wording is pinned and no document anywhere books "
        "a table, so the restaurant that connects its WhatsApp is offered a hairdresser's recipes "
        "and nothing else",
        _CHAIR,
        1,
    ),
    (
        "🔴 the red whatsapp_inbox#124 IS, and the half this rule grew for: the chair booking is "
        "handed by TWO families. Nothing downstream refuses it — both documents parse, both sets "
        "of grants match, every other rule here is green — and the owner opening the WhatsApp card "
        "has to guess which of the two is hers for a decision she already took in Citas",
        {**_CHAIR_PAIR, **_TABLE},
        1,
    ),
    (
        "…and the same on the table side, so the rule cannot be one that only ever fires for "
        "chairs",
        {**_CHAIR, **_TABLE_PAIR},
        1,
    ),
    (
        "both bookings doubled: two complaints, one per booking, because the owner of a salon and "
        "the owner of a restaurant each have their own guess to make",
        {**_CHAIR_PAIR, **_TABLE_PAIR},
        2,
    ),
    (
        "a family that books something else does not cover the row: `customers.create` writes, and "
        "no customer ever sat at it",
        {**_CHAIR, "reservation-from-whatsapp": {"customers.create"}},
        1,
    ),
    (
        "and the row that started it all is judged the same way: delete the chair recipe and this "
        "rule says so, so it cannot be one that only ever fires for tables",
        _TABLE,
        1,
    ),
    (
        "nothing ships at all: both rows are promises nothing keeps",
        {},
        2,
    ),
]


# `(label, file name, document, problems expected)` — the unit tests of `unowned_table_problems`,
# the rule that keeps whatsapp_inbox#60's declared security decision from being prose.
TABLE_SCOPE_CASES = [
    (
        "what this module ships: the unattended table writer books and puts people on the waiting "
        "list, and nothing it holds can touch a booking that already exists",
        TABLE_UNATTENDED,
        _fixture_doc(
            _ai_step(
                "book",
                "auto",
                [TABLE_BOOKING_COMMAND, "reservations.waitlist.create"],
                "Book it.",
            )
        ),
        0,
    ),
    (
        "the regression this rule exists for, and it was measured GREEN before the rule: the "
        "unattended writer is handed the cancel command AND the free search that finds any id",
        TABLE_UNATTENDED,
        _fixture_doc(
            _ai_step(
                "book",
                "auto",
                [TABLE_BOOKING_COMMAND, "reservations.reservations.set_status"],
                "Book it, and cancel it if they ask.",
                queries=["reservations.reservations.list"],
            )
        ),
        2,
    ),
    (
        "a person approves every write there, so the attended family may grow into changing and "
        "cancelling: this rule owes it nothing",
        TABLE_UNNAMED_FAMILY,
        _fixture_doc(
            _ai_step(
                "propose",
                "manual",
                [TABLE_BOOKING_COMMAND, "reservations.reservations.set_status"],
                "Propose it.",
                queries=["reservations.reservations.list"],
            )
        ),
        0,
    ),
    (
        "a step that forgot to say how it runs counts as nobody watching: the family that gets "
        "this wrong is the one where nothing downstream notices",
        TABLE_UNATTENDED,
        _fixture_doc(
            _ai_step(
                "book",
                None,
                [TABLE_BOOKING_COMMAND, "reservations.reservations.update"],
                "Change it.",
            )
        ),
        1,
    ),
    (
        "and it is not anchored on the booking step: a second `auto` step bolted on later owes "
        "exactly the same, which is how this hole would come back",
        TABLE_UNATTENDED,
        _fixture_doc(
            _ai_step("book", "manual", [TABLE_BOOKING_COMMAND], "Propose it."),
            _ai_step("tidy", "auto", ["reservations.reservations.delete"], "Tidy up."),
        ),
        1,
    ),
]


MOVE_CASES = [
    (
        "the shape whatsapp_inbox#74 ships: the appointment writer can book, cancel AND move, it "
        "can list what the customer already has, and it says how moving is done",
        UNNAMED_FAMILY,
        _fixture_doc(
            _ai_step(
                "propose",
                "manual",
                _MOVE_TOOLS,
                f"Book, move or cancel. {MOVE_RULE['en']}",
                queries=_MOVE_QUERIES,
            )
        ),
        0,
    ),
    (
        "the issue itself: the writer books and cancels and has no way to move, so «can you "
        "change it to Thursday?» is answered with «somebody will get back to you»",
        UNNAMED_FAMILY,
        _fixture_doc(
            _ai_step(
                "propose",
                "manual",
                (BOOKING_COMMAND, CANCEL_COMMAND),
                "Book or cancel.",
                queries=_MOVE_QUERIES,
            )
        ),
        1,
    ),
    (
        "it can move and cannot look up what it is moving: the `appointment_id` and the "
        "`customer_id` have to come out of HER diary, so without that query the id is one the "
        "model picked out of the message and `appointments` answers her with a refusal",
        UNNAMED_FAMILY,
        _fixture_doc(
            _ai_step("propose", "manual", _MOVE_TOOLS, f"Move it. {MOVE_RULE['en']}")
        ),
        1,
    ),
    (
        "the sentence reworded away: cancelling and re-booking is still in the same hands, and it "
        "leaves the customer who asked to KEEP her hour with nothing when the second call fails",
        UNNAMED_FAMILY,
        _fixture_doc(
            _ai_step(
                "propose",
                "manual",
                _MOVE_TOOLS,
                "Move it however you like.",
                queries=_MOVE_QUERIES,
            )
        ),
        1,
    ),
    (
        "the Spanish document carries the Spanish wording",
        "appointment-from-whatsapp.es.flow.json",
        _fixture_doc(
            _ai_step(
                "propose",
                "manual",
                _MOVE_TOOLS,
                f"Muévela. {MOVE_RULE['es']}",
                queries=_MOVE_QUERIES,
            )
        ),
        0,
    ),
    (
        "a translation that kept the English sentence dropped the rule for the reader it has",
        "appointment-from-whatsapp.es.flow.json",
        _fixture_doc(
            _ai_step(
                "propose",
                "manual",
                _MOVE_TOOLS,
                f"Muévela. {MOVE_RULE['en']}",
                queries=_MOVE_QUERIES,
            )
        ),
        1,
    ),
    (
        "the half-fix: the tool is handed over and the old «it cannot» order is still there, so "
        "the model keeps refusing and the granted permission is spent on nothing",
        UNNAMED_FAMILY,
        _fixture_doc(
            _ai_step(
                "propose",
                "manual",
                _MOVE_TOOLS,
                f"{MOVE_RULE['en']} Moving is something {CANNOT_MOVE['en']}.",
                queries=_MOVE_QUERIES,
            )
        ),
        1,
    ),
    (
        "the shape whatsapp_inbox#105 ships for the UNATTENDED family, which used to owe the "
        "opposite: with nobody watching it moves too, because since appointments#144 the command "
        "carries who is asking and refuses somebody else's appointment",
        UNATTENDED,
        _fixture_doc(
            _ai_step(
                "book",
                "auto",
                _MOVE_TOOLS,
                f"Book, move or cancel. {MOVE_RULE['en']}",
                queries=_MOVE_QUERIES,
            )
        ),
        0,
    ),
    (
        "🔴 the red whatsapp_inbox#105 IS: the one-chair salon whose automation still answers "
        "«somebody will get back to you» to the most common thing a customer writes, with the "
        "whole point of running unattended being that nobody is there to answer it",
        UNATTENDED,
        _fixture_doc(
            _ai_step(
                "book",
                "auto",
                (BOOKING_COMMAND, CANCEL_COMMAND),
                f"Book or cancel. Moving is something {CANNOT_MOVE['en']}.",
                queries=_MOVE_QUERIES,
            )
        ),
        1,
    ),
    (
        "and the POLICY no longer decides anything here: a writer that never declared one is held "
        "to exactly the same five marks, so no reading of this file makes a missing line the way "
        "to a weaker rule",
        UNNAMED_FAMILY,
        _fixture_doc(
            {
                "id": "propose",
                "kind": "ai",
                "prompt": f"Move it. {MOVE_RULE['en']}",
                "tools": {
                    "commands": list(_MOVE_TOOLS),
                    "queries": list(_MOVE_QUERIES),
                },
            }
        ),
        0,
    ),
    (
        "the unattended writer with no move tool and no «not yet» sentence either: she asks to "
        "move her hour and the model improvises — silence, or a SECOND appointment on top of the "
        "one she was trying to keep",
        UNATTENDED,
        _fixture_doc(
            _ai_step(
                "book",
                "auto",
                (BOOKING_COMMAND, CANCEL_COMMAND),
                "Book or cancel.",
                queries=_MOVE_QUERIES,
            )
        ),
        1,
    ),
    (
        "and a language this battery has no wording for does not buy the unattended family a way "
        "out of moving either: the tool is missing whatever the document is written in",
        "appointment-from-whatsapp.fr.flow.json",
        _fixture_doc(
            _ai_step(
                "book",
                "auto",
                (BOOKING_COMMAND, CANCEL_COMMAND),
                "Réserve ou annule.",
                queries=_MOVE_QUERIES,
            )
        ),
        1,
    ),
    (
        "🔴 the defect whatsapp_inbox#105 found in the UNNAMED_FAMILY family, which has moved since "
        "whatsapp_inbox#74: the tool is there, the rule is there, and the prompt still orders "
        "that the command says nothing about who is asking — so the model omits the field and "
        "`channel` falls back to `staff`, which is the move on the salon's own account",
        UNNAMED_FAMILY,
        _fixture_doc(
            _ai_step(
                "propose",
                "manual",
                _MOVE_TOOLS,
                f"{MOVE_RULE['en']} Unlike cancelling, {MOVE_BLIND['en']}.",
                queries=_MOVE_QUERIES,
            )
        ),
        1,
    ),
    (
        "and the same stale order in the Spanish twin, read out of its own row: a mark that only "
        "knows one language is a mark half the documents can lose",
        "appointment-from-whatsapp.es.flow.json",
        _fixture_doc(
            _ai_step(
                "propose",
                "manual",
                _MOVE_TOOLS,
                f"{MOVE_RULE['es']} A diferencia de anular, {MOVE_BLIND['es']}.",
                queries=_MOVE_QUERIES,
            )
        ),
        1,
    ),
    (
        "the unattended twin owes the same: it is the family that moves with nobody reading, so a "
        "sentence telling it the field is not there is the one that costs most",
        UNATTENDED,
        _fixture_doc(
            _ai_step(
                "book",
                "auto",
                _MOVE_TOOLS,
                f"{MOVE_RULE['en']} Unlike cancelling, {MOVE_BLIND['en']}.",
                queries=_MOVE_QUERIES,
            )
        ),
        1,
    ),
    (
        "a step that cannot book owes nothing: the customer-record step writes, but not into the "
        "diary",
        UNNAMED_FAMILY,
        _fixture_doc(_ai_step("know", "manual", ["customers.create"], "Find or create them.")),
        0,
    ),
    (
        "a language this battery has no wording for is a document it cannot vouch for",
        "appointment-from-whatsapp.fr.flow.json",
        _fixture_doc(
            _ai_step(
                "propose",
                "manual",
                _MOVE_TOOLS,
                f"Déplace-le. {MOVE_RULE['en']}",
                queries=_MOVE_QUERIES,
            )
        ),
        1,
    ),
]


# The mutants of «one customer, and only that one» (whatsapp_inbox#103). The shape every row below
# is a deviation FROM is the one the four templates ship: a `kind: query` resolver keyed on the
# phone WhatsApp vouched for, and a reader that is handed its answer instead of a search box.
_OWN_PHONE = {"phone": "{{" + TRUSTED_PHONE + "}}"}
_DIARY = (OWNED_APPOINTMENTS_QUERY,)


def _own_customer_doc(prompt, queries, params=_OWN_PHONE, resolver_first=True):
    """The shipped shape, with one thing moved — whatever the row under test is about."""
    resolver = _query_step("resolve", params=params)
    reader = _ai_step("book", "auto", [BOOKING_COMMAND], prompt, queries=queries)
    return _fixture_doc(*((resolver, reader) if resolver_first else (reader, resolver)))


_BOOK_FOR_HER = "Book for {{steps.resolve.id}} and for nobody else."

# The mutants of «a key the kernel does not know» (whatsapp_inbox#171).
STEP_KEY_CASES = [
    (
        "the shipped shape: a `command` step sends its payload in `params`",
        {"steps": [{"id": "link", "kind": "command", "command": "x.write",
                    "params": {"a": "{{input.from}}"}, "on_error": "continue"}]},
        0,
    ),
    (
        "\U0001f534 the bug: `payload` is the GRANT's word, and on a step the kernel refuses the "
        "whole document with it — the recipe is offered and cannot be switched on",
        {"steps": [{"id": "link", "kind": "command", "command": "x.write",
                    "payload": {"a": "{{input.from}}"}}]},
        1,
    ),
    (
        "a key the query kind does not take either — the table is per KIND, not one global list",
        {"steps": [{"id": "r", "kind": "query", "query": "x.read", "params": {}, "when": {}}]},
        1,
    ),
    (
        "a step guarded by `run_if` (hub#2066): the kernel takes it on every kind that DOES "
        "something",
        {"steps": [{"id": "sorry", "kind": "notify", "channel": "whatsapp", "template": "",
                    "vars": {"text": "x"}, "run_if": {"steps.a.status": {"eq": "failed"}}}]},
        0,
    ),
    (
        "…but not on a `condition`, which IS a guard: the kernel refuses `run_if` there",
        {"steps": [{"id": "c", "kind": "condition", "when": {},
                    "run_if": {"steps.a.status": {"eq": "failed"}}}]},
        1,
    ),
    (
        "a kind the kernel does not know is refused before any key is read",
        {"steps": [{"id": "s", "kind": "webhook"}]},
        1,
    ),
]


OWN_CUSTOMER_CASES = [
    (
        "the shape the fix ships: the customer is resolved from her own number in a `query` step, "
        "and the model is handed her id instead of the address book",
        UNATTENDED,
        _own_customer_doc(_BOOK_FOR_HER, _DIARY),
        0,
    ),
    (
        "🔴 the row this rule exists for, and the one a test that only looks at the customer's OWN "
        "path lets through: her resolution is PERFECT — resolver on `input.from`, id named in the "
        "prompt — and the model still holds the address book, so «what has María got booked?» is "
        "one search away from her diary. Own path built right is not the foreign path closed",
        UNATTENDED,
        _own_customer_doc(_BOOK_FOR_HER, (DIRECTORY_QUERY,) + _DIARY),
        1,
    ),
    (
        "the address book is refused even where no diary is read at all: a step that only books "
        "can still answer «is María a customer here?» with her phone and her name. The mark is "
        "universal on purpose — every template that resolves a stranger owes the `query` step",
        UNATTENDED,
        _fixture_doc(
            _ai_step("book", "auto", [BOOKING_COMMAND], "Book it.", queries=(DIRECTORY_QUERY,))
        ),
        1,
    ),
    (
        "the pre-fix document: the search box is in two hands at once, and both are counted — the "
        "step that identifies her and the step that books for her",
        UNATTENDED,
        _fixture_doc(
            _ai_step("know", "auto", ["customers.create"], "Who?", queries=(DIRECTORY_QUERY,)),
            _ai_step("book", "auto", [BOOKING_COMMAND], "Book.", queries=(DIRECTORY_QUERY,)),
        ),
        2,
    ),
    (
        "a diary read with no deterministic resolver anywhere: the `customer_id` can only come "
        "from the model, so it is whoever the message named",
        UNATTENDED,
        _fixture_doc(
            _ai_step("book", "auto", [BOOKING_COMMAND], "Book it.", queries=_DIARY)
        ),
        1,
    ),
    (
        "the resolver exists but runs AFTER the reader: `steps.resolve` of a step that has not "
        "run resolves to `null`, so the model improvises the id again",
        UNATTENDED,
        _own_customer_doc(_BOOK_FOR_HER, _DIARY, resolver_first=False),
        2,  # …and nothing after it reads its answer either (mark 5)
    ),
    (
        "the lookup moved into a `query` step and the hole moved with it: the resolver is keyed "
        "on what a model wrote, so the model still picks who this run is about (counted twice — "
        "it reads another step, and it never reads the trusted phone)",
        UNATTENDED,
        _own_customer_doc(_BOOK_FOR_HER, _DIARY, params={"f_name": "{{steps.know.text}}"}),
        2,
    ),
    (
        "the resolver is deterministic and keyed on a NAME: the model is out of the loop and the "
        "wrong customer is picked anyway, because the only identity in this run WhatsApp vouched "
        "for is the number the message came from",
        UNATTENDED,
        _own_customer_doc(_BOOK_FOR_HER, _DIARY, params={"f_name": "Mar\u00eda"}),
        1,
    ),
    (
        "a resolver with no params at all is the whole address book, and its first row is "
        "somebody — just not the somebody who wrote in",
        UNATTENDED,
        _own_customer_doc(_BOOK_FOR_HER, _DIARY, params=None),
        1,
    ),
    (
        "the resolver is right and its answer is never used: the step has no customer, so it "
        "invents one. Closing the lookup without handing over its answer breaks the step instead "
        "of securing it",
        UNATTENDED,
        _own_customer_doc("Book whatever she asked for.", _DIARY),
        2,  # the same defect from both sides: the prompt does not name it (4), nobody reads it (5)
    ),
    (
        "🔴 the resolver is named with ONE brace: `{steps.resolve.id}` is plain text to the "
        "runtime, so the model is handed the words instead of the id and picks the customer "
        "itself — and the step LOOKS wired, which is why mark 4 (a substring match on "
        "`steps.<id>.id`) sails straight past it. This is a bug that really happened while "
        "writing this commit",
        UNATTENDED,
        _own_customer_doc("Book for {steps.resolve.id} and for nobody else.", _DIARY),
        3,  # mark 4 (no resolvable `.id`), mark 5 (nothing reads the answer) and the lost brace
        # itself, which is the only one of the three that NAMES what went wrong
    ),
    (
        "\U0001f534 the SAME lost brace, in the family that reads no diary (the table recipes "
        "whatsapp_inbox#104 brought): `.found` still resolves, so mark 5 is satisfied, and mark 4 "
        "never runs because nothing here reads a diary — so the one reference that carries the "
        "IDENTITY can sit in the prompt as plain text with the battery green. This is the shape "
        "`str.format` really produced while these templates were being written",
        UNATTENDED,
        _fixture_doc(
            _query_step("resolve", params=_OWN_PHONE),
            _ai_step(
                "book",
                "auto",
                [BOOKING_COMMAND],
                "On file: {{steps.resolve.found}}. Book for {steps.resolve.id}.",
            ),
        ),
        1,
    ),
    (
        "\U0001f534 the lookup whatsapp_inbox#165 is about: deterministic, keyed on the trusted "
        "phone, its answer used — and made over `customers.list`, whose `f_phone` is a LIKE on the "
        "raw text. `34600111222` never finds the card typed `600 111 222`, so the customer of "
        "years is «not on file» and gets a second card. Nothing else here is wrong, which is why "
        "only this mark can see it",
        UNATTENDED,
        _fixture_doc(
            _query_step("find", DIRECTORY_QUERY, {"f_phone": "+{{" + TRUSTED_PHONE + "}}"}),
            _ai_step("know", "auto", ["customers.create"], "On file: {{steps.find.found}}."),
        ),
        1,
    ),
    (
        "the same text lookup where a diary is read: the address-book step is no resolver, so the "
        "reader has none before it either — two reds for one wrong query",
        UNATTENDED,
        _fixture_doc(
            _query_step("resolve", DIRECTORY_QUERY, {"f_phone": "+{{" + TRUSTED_PHONE + "}}"}),
            _ai_step("book", "auto", [BOOKING_COMMAND], _BOOK_FOR_HER, queries=_DIARY),
        ),
        2,
    ),
    (
        "silent on a deterministic read of the address book that is not about the sender's number: "
        "the mark is about looking a PHONE up as text, not about `customers.list` as such",
        UNNAMED_FAMILY,
        _fixture_doc(
            _query_step("vips", DIRECTORY_QUERY, {"f_tag": "vip"}),
            _ai_step("reply", "manual", [], "VIPs on file: {{steps.vips.count}}."),
        ),
        0,
    ),
    (
        "silent where nothing is owed: a step that reads no diary and holds no address book",
        UNNAMED_FAMILY,
        _fixture_doc(_ai_step("reply", "manual", [], "Say hello back.")),
        0,
    ),
]



def _wa_doc(condition=None, mapping=None, steps=None):
    """A document carrying the trigger these templates really ship: the core's WhatsApp event."""
    return {
        "schema_version": 1,
        "triggers": [
            {
                "kind": "event",
                "event": WHATSAPP_EVENT,
                "filter": TEXT_ONLY if condition is None else condition,
                "input": {"from": "event.from", "text": "event.text"}
                if mapping is None
                else mapping,
            }
        ],
        "steps": [_notify_step()] if steps is None else list(steps),
    }


# The filter as it stood before whatsapp_inbox#90 — «anything with words in it».
TEXT_ONLY = {"event.text": {"neq": ""}}
# …and as it ships now. `neq` and not `eq` on purpose: see `only_the_customer_problems`.
LIVE_INBOUND = {
    "event.text": {"neq": ""},
    "event.direction": {"neq": "outbound"},
    "event.source": {"neq": "history"},
}


def _contact_notify(step_id="tell"):
    """The tempting mistake: address the reply by the field that is right in an echo."""
    step = _notify_step(step_id)
    step["to"]["params"] = {"f_wa_contact_id": "input.contact"}
    return step


# The two-trigger mutants of whatsapp_inbox#101. `_two` is `_wa_doc` with a second trigger, which
# is the shape the tap needs and the shape that can book somebody twice.
def _two(second_filter, second_input=None):
    doc = _wa_doc(LIVE_INBOUND)
    doc["triggers"].append(
        {
            "kind": "event",
            "event": WHATSAPP_EVENT,
            "filter": second_filter,
            "input": second_input or {"from": "event.from", "text": "event.reply_title"},
        }
    )
    return doc


_TAP_FILTER = {
    "event.text": {"eq": ""},
    "event.reply_id": {"neq": ""},
    "event.direction": {"neq": "outbound"},
    "event.source": {"neq": "history"},
}

# `(label, file name, document, problems expected)` — the mutants of «a customer, and only now».
ONLY_CUSTOMER_CASES = [
    (
        "the shape whatsapp_inbox#90 ships: the owner's echo and the backlog are both refused, "
        "and a core at the floor still wakes up",
        UNNAMED_FAMILY,
        _wa_doc(LIVE_INBOUND),
        0,
    ),
    (
        "the filter as it was: «anything with words in it» answers the owner's own reply AND "
        "every message of the 180-day backlog",
        UNNAMED_FAMILY,
        _wa_doc(TEXT_ONLY),
        2,
    ),
    (
        "who spoke, without when: the backlog still arrives",
        UNNAMED_FAMILY,
        _wa_doc({**TEXT_ONLY, "event.direction": {"neq": "outbound"}}),
        1,
    ),
    (
        "when, without who: the owner is still answered by her own automation",
        UNNAMED_FAMILY,
        _wa_doc({**TEXT_ONLY, "event.source": {"neq": "history"}}),
        1,
    ),
    (
        "🔴 `eq` reads right and is the regression: on a core at this module's declared floor the "
        "path is absent, `json_eq(Null, \"inbound\")` is false, and the automation is off with "
        "nothing said",
        UNNAMED_FAMILY,
        _wa_doc(
            {
                **TEXT_ONLY,
                "event.direction": {"eq": "inbound"},
                "event.source": {"neq": "history"},
            }
        ),
        1,
    ),
    (
        "…and `in` is the same trap with a list around it",
        UNNAMED_FAMILY,
        _wa_doc(
            {
                **TEXT_ONLY,
                "event.direction": {"in": ["inbound"]},
                "event.source": {"neq": "history"},
            }
        ),
        1,
    ),
    (
        "…and asking whether the field is THERE is worse than either: it blocks the floor-level "
        "core and lets the echo through, because `outbound` exists just as much as `inbound` does",
        UNNAMED_FAMILY,
        _wa_doc(
            {
                **TEXT_ONLY,
                "event.direction": {"exists": True},
                "event.source": {"neq": "history"},
            }
        ),
        2,
    ),
    (
        "…and `eq` on `source` fails the same way, one field over",
        UNNAMED_FAMILY,
        _wa_doc(
            {
                **TEXT_ONLY,
                "event.direction": {"neq": "outbound"},
                "event.source": {"eq": "live"},
            }
        ),
        1,
    ),
    (
        "the filter written inside out answers the salon and ignores the customer — two harms, "
        "and the floor-level core is the one thing it still gets right",
        UNNAMED_FAMILY,
        _wa_doc(
            {
                **TEXT_ONLY,
                "event.direction": {"neq": "inbound"},
                "event.source": {"neq": "history"},
            }
        ),
        2,
    ),
    (
        "an operator this battery cannot copy is refused, not waved through: a filter it judges "
        "with a guess is worse than one it does not judge",
        UNNAMED_FAMILY,
        _wa_doc({**LIVE_INBOUND, "event.direction": {"contains": "in"}}),
        1,
    ),
    (
        "🔴 the reply addressed by `event.contact` — the field that is RIGHT in an echo, and "
        "absent on a core at the floor, where it hands the query a `null`",
        UNNAMED_FAMILY,
        _wa_doc(
            LIVE_INBOUND,
            mapping={"from": "event.from", "text": "event.text", "contact": "event.contact"},
            steps=[_contact_notify()],
        ),
        1,
    ),
    (
        "…and addressing the reply by an input key the trigger never maps is the same `null` "
        "arriving by a shorter road",
        UNNAMED_FAMILY,
        _wa_doc(LIVE_INBOUND, steps=[_contact_notify()]),
        1,
    ),
    (
        "every notify step is judged, not the first: two replies wrongly addressed are two "
        "customers who get somebody else's message",
        UNNAMED_FAMILY,
        _wa_doc(LIVE_INBOUND, steps=[_contact_notify("acknowledge"), _contact_notify("confirm")]),
        2,
    ),
    (
        "the unattended family is held to exactly the same promise: nobody is watching there",
        UNATTENDED,
        _wa_doc(TEXT_ONLY),
        2,
    ),
    (
        "a template that waits on some other event is not this rule's business",
        UNNAMED_FAMILY,
        {
            "schema_version": 1,
            "triggers": [{"kind": "event", "event": "sale.completed", "filter": {}}],
            "steps": [_notify_step()],
        },
        0,
    ),
    (
        "the pair this issue ships: one trigger waits for words, the other for a tap, and no "
        "message satisfies both — disjoint by construction, not by luck",
        UNNAMED_FAMILY,
        _two(_TAP_FILTER),
        0,
    ),
    (
        "🔴 the worst failure this channel has: two triggers that both match ONE message, so the "
        "hub starts two runs of a booking recipe over it and the customer ends with two "
        "appointments — both runs `done`, nothing reported",
        UNNAMED_FAMILY,
        _two(LIVE_INBOUND),
        2,
    ),
    (
        "🔴 the overlap that reads as disjoint: the tap trigger forgets to demand the ABSENCE of "
        "text, so every word the customer writes matches it too",
        UNNAMED_FAMILY,
        _two({k: v for k, v in _TAP_FILTER.items() if k != "event.text"}),
        2,
    ),
]


SILENCE_CASES = [
    (
        "an automation that books and then says so — in the words the booking step wrote for the "
        "customer — is the whole point",
        _fixture_doc(
            _ai_step("book", "manual", ["appointments.appointments.create"]),
            _notify_step("tell", "{{steps.book.text}}"),
        ),
        0,
    ),
    (
        "…and the hub trims the path, so the spaced spelling is the same quotation",
        _fixture_doc(
            _ai_step("book", "manual", ["appointments.appointments.create"]),
            _notify_step("tell", "{{ steps.book.text }}"),
        ),
        0,
    ),
    (
        "a notify AFTER the booking that says something of its own («Done.») is not the "
        "confirmation: the day, the hour and the professional only exist in the booking step's "
        "own text, and a fixed sentence cannot carry them (reviewer mutant N7 on "
        "whatsapp_inbox#58)",
        _fixture_doc(
            _ai_step("book", "manual", ["appointments.appointments.create"]),
            _notify_step("tell", "Done."),
        ),
        1,
    ),
    (
        "quoting SOME other step is not quoting the one that booked",
        _fixture_doc(
            _ai_step("who", "manual", ["customers.create"]),
            _ai_step("book", "manual", ["appointments.appointments.create"]),
            _notify_step("tell", "{{steps.who.text}}"),
        ),
        1,
    ),
    (
        "an automation that books and says NOTHING leaves the customer waiting",
        _fixture_doc(_ai_step("book", "manual", ["appointments.appointments.create"])),
        1,
    ),
    (
        "the acknowledgement sent BEFORE booking is not a confirmation",
        _fixture_doc(
            _notify_step("acknowledge", "we got your message"),
            _ai_step("book", "manual", ["appointments.appointments.create"]),
        ),
        1,
    ),
    (
        "a step that proposes nothing owes the customer nothing",
        _fixture_doc({"id": "look", "kind": "ai", "policy": "auto", "prompt": "", "tools": {"queries": ["customers.list"]}}),
        0,
    ),
    (
        "the LAST step that can book is the one that has to be answered",
        _fixture_doc(
            _ai_step("who", "manual", ["customers.create"]),
            _notify_step("half", "found you"),
            _ai_step("book", "manual", ["appointments.appointments.create"]),
        ),
        1,
    ),
    (
        "ONE HOP is a confirmation: the message can come from a step in between, as long as that "
        "step carries the booking step's own words (whatsapp_inbox#67)",
        _fixture_doc(
            _ai_step("book", "manual", ["appointments.appointments.create"]),
            _relay_step("reply", "book"),
            _notify_step("tell", "{{steps.reply.text}}"),
        ),
        0,
    ),
    (
        "…and a hop that quotes NOBODY is the same «Done.» wearing an extra step: the day, the "
        "hour and the professional never left the booking step",
        _fixture_doc(
            _ai_step("book", "manual", ["appointments.appointments.create"]),
            {"id": "reply", "kind": "ai", "policy": "manual", "prompt": "Say something nice."},
            _notify_step("tell", "{{steps.reply.text}}"),
        ),
        1,
    ),
]


# `(label, document, problems expected)` — the mutants of «a «no» reaches the customer too».
REFUSAL_CASES = [
    (
        "a step that declares `output` under `manual` can never BE rejected: the kernel refuses "
        "its proposals by name (a proposal ends the turn and the fields would never arrive), so "
        "it owes no `on_reject` and it is not the writer this rule is about. It is the shape the "
        "attended family uses to hand over the slots she taps (whatsapp_inbox#109)",
        _fixture_doc(
            _ai_step(
                "book", "manual", ["appointments.appointments.create"], on_reject="continue"
            ),
            {
                "id": "reply",
                "kind": "ai",
                "policy": "manual",
                "prompt": "{{steps.book.text}} {{steps.book.status}}",
                "tools": {"commands": ["appointments.availability.slots"]},
                "output": {"slots": {"type": "options", "describe": "what she may tap"}},
            },
            _notify_step("tell", "{{steps.reply.text}}"),
        ),
        0,
    ),
    (
        "the shape whatsapp_inbox#67 ships: the booking step survives a «no» and the step that "
        "writes the reply knows how the turn ended",
        _fixture_doc(
            _ai_step(
                "book", "manual", ["appointments.appointments.create"], on_reject="continue"
            ),
            _relay_step("reply", "book"),
            _notify_step("tell", "{{steps.reply.text}}"),
        ),
        0,
    ),
    (
        "without `on_reject` the kernel cancels the run AT the rejection, so the notify after it "
        "is dead code and the customer waits forever",
        _fixture_doc(
            _ai_step("book", "manual", ["appointments.appointments.create"]),
            _relay_step("reply", "book"),
            _notify_step("tell", "{{steps.reply.text}}"),
        ),
        1,
    ),
    (
        "…and saying `cancel` out loud is the same ending, not an exemption",
        _fixture_doc(
            _ai_step("book", "manual", ["appointments.appointments.create"], on_reject="cancel"),
            _relay_step("reply", "book"),
            _notify_step("tell", "{{steps.reply.text}}"),
        ),
        1,
    ),
    (
        "surviving the «no» is only half: a notify that sends the booking step's own text tells a "
        "customer whose appointment was just refused the day, the hour and the professional she "
        "is NOT getting",
        _fixture_doc(
            _ai_step(
                "book", "manual", ["appointments.appointments.create"], on_reject="continue"
            ),
            _notify_step("tell", "{{steps.book.text}}"),
        ),
        1,
    ),
    (
        "a step in between that never reads `status` is just as blind — it relays the same "
        "sentence the model wrote before anybody decided",
        _fixture_doc(
            _ai_step(
                "book", "manual", ["appointments.appointments.create"], on_reject="continue"
            ),
            {"id": "reply", "kind": "ai", "policy": "manual", "prompt": "Send {{steps.book.text}}"},
            _notify_step("tell", "{{steps.reply.text}}"),
        ),
        1,
    ),
    (
        "both halves missing is two defects, not one: the run dies AND what it would have sent "
        "was wrong",
        _fixture_doc(
            _ai_step("book", "manual", ["appointments.appointments.create"]),
            _notify_step("tell", "{{steps.book.text}}"),
        ),
        2,
    ),
    (
        "a missing `policy` key is `manual` — the default the kernel applies, and the one that "
        "can be rejected",
        _fixture_doc(
            {
                "id": "book",
                "kind": "ai",
                "prompt": "",
                "tools": {"commands": ["appointments.appointments.create"]},
            },
            _relay_step("reply", "book"),
            _notify_step("tell", "{{steps.reply.text}}"),
        ),
        1,
    ),
    (
        "`auto` never asks anybody, so there is no «no» to survive: the `-unattended` family is "
        "silent here on purpose",
        _fixture_doc(
            _ai_step("book", "auto", ["appointments.appointments.create"]),
            _notify_step("tell", "{{steps.book.text}}"),
        ),
        0,
    ),
    (
        "a document that says nothing to anybody is `silence_problems`, not this rule — one hole, "
        "one owner",
        _fixture_doc(_ai_step("book", "manual", ["appointments.appointments.create"])),
        0,
    ),
    (
        "and a document that proposes nothing owes nobody an answer",
        _fixture_doc(
            {"id": "look", "kind": "ai", "policy": "manual", "prompt": "", "tools": {"queries": ["customers.list"]}},
            _notify_step("tell", "hello"),
        ),
        0,
    ),
]



def _assistant(step_id="book", on_error="continue"):
    step = _ai_step(step_id, "auto", ["appointments.appointments.create"])
    if on_error is not None:
        step["on_error"] = on_error
    return step


def _apology(writer="book", text="Sorry, someone from the team will answer you here soon.", op="eq"):
    step = _notify_step("sorry", text)
    step["run_if"] = {f"steps.{writer}.status": {op: "failed"}}
    return step


def _stop_if_failed(writer="book", op="neq"):
    return {"id": "answered", "kind": "condition", "when": {f"steps.{writer}.status": {op: "failed"}}}


# `(label, document, problems expected)` for `assistant_failure_problems` (whatsapp_inbox#122).
ASSISTANT_FAILURE_CASES = [
    (
        "the shape the fix ships: the turn may fail and carry on, the apology runs only if it did, "
        "the run ends there if it did, the confirmation follows",
        _fixture_doc(
            _notify_step("ack", "one moment"), _assistant(), _apology(), _stop_if_failed(),
            _notify_step("confirm", "{{steps.book.text}}"),
        ),
        0,
    ),
    (
        "an assistant turn nobody was told to wait for is not this rule's business",
        _fixture_doc(_assistant(on_error=None), _notify_step("confirm", "{{steps.book.text}}")),
        0,
    ),
    (
        "\U0001f534 the bug, as it shipped: «one moment», then a turn that dies with the run",
        _fixture_doc(
            _notify_step("ack", "one moment"), _assistant(on_error=None),
            _notify_step("confirm", "{{steps.book.text}}"),
        ),
        3,
    ),
    (
        "`on_error` alone: the run survives and sends her the EMPTY text of a failed turn",
        _fixture_doc(
            _notify_step("ack", "one moment"), _assistant(),
            _notify_step("confirm", "{{steps.book.text}}"),
        ),
        2,
    ),
    (
        "the apology without `on_error`: the kernel ends the run before it is ever reached",
        _fixture_doc(
            _notify_step("ack", "one moment"), _assistant(on_error=None), _apology(),
            _stop_if_failed(),
        ),
        1,
    ),
    (
        "an apology guarded the wrong way round goes out every time the assistant ANSWERED",
        _fixture_doc(
            _notify_step("ack", "one moment"), _assistant(), _apology(op="neq"), _stop_if_failed(),
        ),
        1,
    ),
    (
        "an apology that quotes the step that failed sends her an empty message",
        _fixture_doc(
            _notify_step("ack", "one moment"), _assistant(), _apology(text="{{steps.book.text}}"),
            _stop_if_failed(),
        ),
        1,
    ),
    (
        "an apology with no words at all",
        _fixture_doc(
            _notify_step("ack", "one moment"), _assistant(), _apology(text="  "), _stop_if_failed(),
        ),
        1,
    ),
    (
        "without the condition the confirmation still goes out after the apology",
        _fixture_doc(
            _notify_step("ack", "one moment"), _assistant(), _apology(),
            _notify_step("confirm", "{{steps.book.text}}"),
        ),
        1,
    ),
    (
        "a condition that stops the run when the assistant ANSWERED",
        _fixture_doc(
            _notify_step("ack", "one moment"), _assistant(), _apology(), _stop_if_failed(op="eq"),
        ),
        1,
    ),
    (
        "the apology addressed to somebody other than the customer who was acknowledged",
        _fixture_doc(
            _notify_step("ack", "one moment"), _assistant(),
            {**_apology(), "to": {"query": "staff.members.list", "field": "phone"}},
            _stop_if_failed(),
        ),
        1,
    ),
    (
        "EVERY turn she waits on is judged, not only the first: the second one fails unanswered",
        _fixture_doc(
            _notify_step("ack", "one moment"), _assistant("know"), _apology("know"),
            _stop_if_failed("know"), _assistant("book", on_error=None),
            _notify_step("confirm", "{{steps.book.text}}"),
        ),
        3,
    ),
]


def _slot_assistant(step_id="book"):
    step = _assistant(step_id)
    step["output"] = {"slots": {"type": "options", "describe": "the slots she can tap"}}
    return step


def _silence_apology(writer="book", text="Sorry, someone from the team will answer you here soon.",
                     guard=None):
    step = _notify_step("sorry_silent", text)
    step["run_if"] = guard if guard is not None else {
        f"steps.{writer}.text": {"in": ["", None]}, f"steps.{writer}.slots": {"eq": []},
    }
    return step


def _reply(writer="book", guard=None):
    step = _notify_step("confirm", "{{steps.%s.text}}" % writer)
    step["run_if"] = guard if guard is not None else {
        f"steps.{writer}.text": {"exists": True, "neq": ""},
    }
    return step


# `(label, document, problems expected)` for `assistant_silence_problems` (whatsapp_inbox#239).
ASSISTANT_SILENCE_CASES = [
    (
        "the shape the fix ships: a failed turn is apologised for and stops; a turn with no words "
        "and nothing to tap is apologised for; the reply only goes out when it has words",
        _fixture_doc(
            _notify_step("ack", "one moment"), _slot_assistant(), _apology(), _stop_if_failed(),
            _silence_apology(), _reply(),
        ),
        0,
    ),
    (
        "a turn that declares nothing to tap is silent on its text alone",
        _fixture_doc(
            _notify_step("ack", "one moment"), _assistant(), _apology(), _stop_if_failed(),
            _silence_apology(guard={"steps.book.text": {"in": ["", None]}}), _reply(),
        ),
        0,
    ),
    (
        "a turn whose words never reach her (it only makes sure the card exists) is not judged",
        _fixture_doc(
            _notify_step("ack", "one moment"), _assistant("know"), _apology("know"),
            _stop_if_failed("know"),
        ),
        0,
    ),
    (
        "\U0001f534 the bug, as #122 shipped it: a `done` turn with no words sends her an EMPTY "
        "message, and nothing else",
        _fixture_doc(
            _notify_step("ack", "one moment"), _slot_assistant(), _apology(), _stop_if_failed(),
            _notify_step("confirm", "{{steps.book.text}}"),
        ),
        2,
    ),
    (
        "the reply guarded but no apology: she is not sent an empty message — she is sent nothing",
        _fixture_doc(
            _notify_step("ack", "one moment"), _slot_assistant(), _apology(), _stop_if_failed(),
            _reply(),
        ),
        1,
    ),
    (
        "the apology but an unguarded reply: she gets the apology AND an empty message",
        _fixture_doc(
            _notify_step("ack", "one moment"), _slot_assistant(), _apology(), _stop_if_failed(),
            _silence_apology(), _notify_step("confirm", "{{steps.book.text}}"),
        ),
        1,
    ),
    (
        "a reply guarded with `neq \"\"` alone lets a MISSING text through, which the kernel "
        "refuses and the run dies",
        _fixture_doc(
            _notify_step("ack", "one moment"), _slot_assistant(), _apology(), _stop_if_failed(),
            _silence_apology(), _reply(guard={"steps.book.text": {"neq": ""}}),
        ),
        1,
    ),
    (
        "an apology on the text alone when the turn declares slots: no words but slots to tap is "
        "an ANSWER, and she would be told nobody can help while being offered the list",
        _fixture_doc(
            _notify_step("ack", "one moment"), _slot_assistant(), _apology(), _stop_if_failed(),
            _silence_apology(guard={"steps.book.text": {"in": ["", None]}}), _reply(),
        ),
        1,
    ),
    (
        "an apology on `eq \"\"` only: a turn with no text key at all is not caught",
        _fixture_doc(
            _notify_step("ack", "one moment"), _slot_assistant(), _apology(), _stop_if_failed(),
            _silence_apology(guard={"steps.book.text": {"eq": ""}, "steps.book.slots": {"eq": []}}),
            _reply(),
        ),
        1,
    ),
    (
        "the silence apology BEFORE the failure stop: a failed turn with no words is apologised "
        "for twice",
        _fixture_doc(
            _notify_step("ack", "one moment"), _slot_assistant(), _apology(), _silence_apology(),
            _stop_if_failed(), _reply(),
        ),
        1,
    ),
    (
        "an apology that quotes the words that were never written: not fixed words, and one more "
        "message sending her the empty text",
        _fixture_doc(
            _notify_step("ack", "one moment"), _slot_assistant(), _apology(), _stop_if_failed(),
            _silence_apology(text="{{steps.book.text}}"), _reply(),
        ),
        2,
    ),
    (
        "the apology addressed to somebody other than the customer who was acknowledged",
        _fixture_doc(
            _notify_step("ack", "one moment"), _slot_assistant(), _apology(), _stop_if_failed(),
            {**_silence_apology(), "to": {"query": "staff.members.list", "field": "phone"}},
            _reply(),
        ),
        1,
    ),
]


ENDING_CASES = [
    (
        "the shape whatsapp_inbox#70 ships: the booking step survives BOTH endings and the step "
        "that writes the reply knows all three words a status can carry",
        _fixture_doc(
            dict(
                _ai_step(
                    "book", "manual", ["appointments.appointments.create"], on_reject="continue"
                ),
                on_expire="continue",
                on_error="continue",
            ),
            _ending_relay("reply", "book"),
            _notify_step("tell", "{{steps.reply.text}}"),
        ),
        0,
    ),
    (
        "neither key: the run dies at the expiry AND at the failure, and both are the same "
        "customer left waiting for ever — two holes, two problems",
        _fixture_doc(
            _ai_step(
                "book", "manual", ["appointments.appointments.create"], on_reject="continue"
            ),
            _ending_relay("reply", "book"),
            _notify_step("tell", "{{steps.reply.text}}"),
        ),
        2,
    ),
    (
        "surviving the failure but not the silence: nobody opens the tray and the sweep cancels "
        "the run at 72 h",
        _fixture_doc(
            dict(
                _ai_step(
                    "book", "manual", ["appointments.appointments.create"], on_reject="continue"
                ),
                on_error="continue",
            ),
            _ending_relay("reply", "book"),
            _notify_step("tell", "{{steps.reply.text}}"),
        ),
        1,
    ),
    (
        "…and the other way round: the salon approves, the slot has gone, and the run ends as "
        "`failed` before the notify",
        _fixture_doc(
            dict(
                _ai_step(
                    "book", "manual", ["appointments.appointments.create"], on_reject="continue"
                ),
                on_expire="continue",
            ),
            _ending_relay("reply", "book"),
            _notify_step("tell", "{{steps.reply.text}}"),
        ),
        1,
    ),
    (
        "saying the kernel's own defaults out loud is the same two endings, not an exemption",
        _fixture_doc(
            dict(
                _ai_step(
                    "book", "manual", ["appointments.appointments.create"], on_reject="continue"
                ),
                on_expire="reject",
                on_error="stop",
            ),
            _ending_relay("reply", "book"),
            _notify_step("tell", "{{steps.reply.text}}"),
        ),
        2,
    ),
    (
        "surviving is only half: a relay that was never told about `expired` reads it as «nothing "
        "was refused» and sends her the booking that never happened",
        _fixture_doc(
            dict(
                _ai_step(
                    "book", "manual", ["appointments.appointments.create"], on_reject="continue"
                ),
                on_expire="continue",
                on_error="continue",
            ),
            _ending_relay("reply", "book", names=("failed",)),
            _notify_step("tell", "{{steps.reply.text}}"),
        ),
        1,
    ),
    (
        "…and the same for `failed`",
        _fixture_doc(
            dict(
                _ai_step(
                    "book", "manual", ["appointments.appointments.create"], on_reject="continue"
                ),
                on_expire="continue",
                on_error="continue",
            ),
            _ending_relay("reply", "book", names=("expired",)),
            _notify_step("tell", "{{steps.reply.text}}"),
        ),
        1,
    ),
    (
        "one relay quoted by TWO notify steps is one prompt, not two defects",
        _fixture_doc(
            dict(
                _ai_step(
                    "book", "manual", ["appointments.appointments.create"], on_reject="continue"
                ),
                on_expire="continue",
                on_error="continue",
            ),
            _ending_relay("reply", "book", names=()),
            _notify_step("tell", "{{steps.reply.text}}"),
            _notify_step("tell_again", "{{steps.reply.text}}"),
        ),
        2,
    ),
    (
        "a relay that never reads `status` at all is `mute_refusal_problems`'s hole, not this "
        "one — one hole, one owner",
        _fixture_doc(
            dict(
                _ai_step(
                    "book", "manual", ["appointments.appointments.create"], on_reject="continue"
                ),
                on_expire="continue",
                on_error="continue",
            ),
            {"id": "reply", "kind": "ai", "policy": "manual", "prompt": "Send {{steps.book.text}}"},
            _notify_step("tell", "{{steps.reply.text}}"),
        ),
        0,
    ),
    (
        "`auto` parks nothing: there is no tray to expire, and a broken tool call comes back to "
        "the model as a tool result instead of failing the step (the `-unattended` family)",
        _fixture_doc(
            _ai_step("book", "auto", ["appointments.appointments.create"]),
            _notify_step("tell", "{{steps.book.text}}"),
        ),
        0,
    ),
    (
        "a document that says nothing to anybody is `silence_problems`, not this rule",
        _fixture_doc(_ai_step("book", "manual", ["appointments.appointments.create"])),
        0,
    ),
    (
        "and a document that proposes nothing has no ending to survive",
        _fixture_doc(
            {"id": "look", "kind": "ai", "policy": "manual", "prompt": "", "tools": {"queries": ["customers.list"]}},
            _notify_step("tell", "hello"),
        ),
        0,
    ),
    (
        "a step that declares `output` under `manual` can never park a proposal, so it is not the "
        "writer this rule is about either (whatsapp_inbox#109)",
        _fixture_doc(
            dict(
                _ai_step(
                    "book", "manual", ["appointments.appointments.create"], on_reject="continue"
                ),
                on_expire="continue",
                on_error="continue",
            ),
            {
                "id": "reply",
                "kind": "ai",
                "policy": "manual",
                "prompt": "{{steps.book.text}} {{steps.book.status}} `expired` `failed`",
                "tools": {"commands": ["appointments.availability.slots"]},
                "output": {"slots": {"type": "options", "describe": "what she may tap"}},
            },
            _notify_step("tell", "{{steps.reply.text}}"),
        ),
        0,
    ),
]


_KNOWN_OPS = {
    "customers.list",
    "customers.create",
    "appointments.availability.slots",
    "appointments.appointments.create",
    "appointments.appointments.cancel",
    "appointments.appointments.list_for_customer",
}

TOOL_CASES = [
    (
        "a prompt that only names what the step handed it is fine",
        _fixture_doc(
            _ai_step("s", "manual", ["appointments.appointments.create"], "Propose `appointments.appointments.create` with the slot."),
        ),
        0,
    ),
    (
        "a prompt that orders a command the step never declared",
        _fixture_doc(
            _ai_step("s", "manual", ["appointments.appointments.create"], "If they cancel, call `appointments.appointments.cancel`."),
        ),
        1,
    ),
    (
        "a prompt that orders a QUERY the step never declared",
        _fixture_doc(
            {"id": "s", "kind": "ai", "policy": "manual", "tools": {"queries": ["customers.list"]},
             "prompt": "Look them up with `customers.list` and their visits with `appointments.appointments.list_for_customer`."},
        ),
        1,
    ),
    (
        "a word that is not an operation of any module is prose, not a tool",
        _fixture_doc(
            _ai_step("s", "manual", ["appointments.appointments.create"], "Put the estimate in `internal_notes` and the ask in `notes`."),
        ),
        0,
    ),
    (
        "a step that hands over queries AND commands is judged against both",
        _fixture_doc(
            {"id": "s", "kind": "ai", "policy": "manual",
             "tools": {"queries": ["customers.list"], "commands": ["appointments.appointments.cancel"]},
             "prompt": "Find them with `customers.list`, then `appointments.appointments.cancel`."},
        ),
        0,
    ),
    (
        "a notify step carries no prompt and owes nothing",
        _fixture_doc(_notify_step("tell", "your appointment is cancelled")),
        0,
    ),
]


ORDER_CASES = [
    (
        "a tool the prompt names is a tool the prompt spends",
        _fixture_doc(
            _ai_step("s", "manual", ["appointments.appointments.create"], "Propose `appointments.appointments.create`."),
        ),
        0,
    ),
    (
        "a command handed over that the prompt never names is a door left open",
        _fixture_doc(
            _ai_step(
                "s",
                "manual",
                ["appointments.appointments.create", "appointments.appointments.cancel"],
                "Propose `appointments.appointments.create`.",
            ),
        ),
        1,
    ),
    (
        "a QUERY handed over that the prompt never names, the same",
        _fixture_doc(
            {"id": "s", "kind": "ai", "policy": "manual",
             "tools": {"queries": ["customers.list", "appointments.appointments.list_for_customer"]},
             "prompt": "Find them with `customers.list`."},
        ),
        1,
    ),
    (
        "a step that hands nothing over owes nothing",
        _fixture_doc({"id": "s", "kind": "ai", "policy": "manual", "prompt": "Answer in one line.", "tools": {}}),
        0,
    ),
    ("a notify step hands no tools", _fixture_doc(_notify_step()), 0),
]


def _budget_step(max_iters):
    return {**_ai_step("s", "manual", ["appointments.appointments.create"]), "max_iters": max_iters}


BUDGET_CASES = [
    ("at the cap is what the module ships", _fixture_doc(_budget_step(MAX_ITERS_CAP)), 0),
    ("one past the cap is a document no hub saves", _fixture_doc(_budget_step(MAX_ITERS_CAP + 1)), 1),
    ("zero turns is not a step", _fixture_doc(_budget_step(0)), 1),
    ("a step that leaves it unset takes the hub's default", _fixture_doc(_ai_step("s", "manual", [])), 0),
    (
        "🔴 one turn and a tool in its hands: the call spends the only turn it has, the step dies "
        "with `flow.agent_max_iters` and she is answered by nobody",
        _fixture_doc(_ai_step("s", "manual", ["appointments.availability.slots"], max_iters=1)),
        1,
    ),
    (
        "two turns is the floor that works: one to ask, one to answer",
        _fixture_doc(_ai_step("s", "manual", ["appointments.availability.slots"], max_iters=2)),
        0,
    ),
    (
        "…and a step with no tools at all is fine with one: there is nothing to call",
        _fixture_doc(_ai_step("s", "manual", [], max_iters=1)),
        0,
    ),
]

_FIXTURE_ENUMS = {"appointments.appointments.cancel": {"channel": ["staff", "customer"]}}


def _enum_step(prompt, commands=("appointments.appointments.cancel",)):
    return _fixture_doc(_ai_step("s", "manual", list(commands), prompt))


ENUM_CASES = [
    (
        "`customer` is one of the two words the cancel gate accepts",
        _enum_step("Propose `appointments.appointments.cancel` with `channel` set to `customer`."),
        0,
    ),
    (
        "`whatsapp` — what the issue said — is a proposal the hub refuses after approval",
        _enum_step("Propose `appointments.appointments.cancel` with `channel` set to `whatsapp`."),
        1,
    ),
    (
        "the Spanish order reads the same",
        _enum_step("Propón `appointments.appointments.cancel` con `channel` puesto a `whatsapp`."),
        1,
    ),
    ("and so does an equals sign", _enum_step("`appointments.appointments.cancel`, `channel` = `whatsapp`"), 1),
    (
        "a value for a field no handed command constrains is prose",
        _enum_step("`appointments.appointments.cancel`; filter by `phone` = `+{{input.from}}`."),
        0,
    ),
    (
        "a command the step never handed over constrains nothing here",
        _enum_step("`appointments.appointments.create`, `channel` set to `whatsapp`", ("appointments.appointments.create",)),
        0,
    ),
]


IDENTITY_CASES = [
    (
        "the order that works: who is asking travels with the customer channel",
        _enum_step(
            "Cancel it with `appointments.appointments.cancel`: that `appointment_id`, a `reason`, "
            "`channel` set to `customer` and the `customer_id` you looked up."
        ),
        0,
    ),
    (
        "whatsapp_inbox#82 as it shipped: the channel is ordered and nobody is named",
        _enum_step(
            "Cancel it with `appointments.appointments.cancel`: that `appointment_id`, a `reason`, "
            "and `channel` set to `customer`."
        ),
        1,
    ),
    (
        "the Spanish order reads the same",
        _enum_step(
            "Anulala con `appointments.appointments.cancel`: ese `appointment_id`, un `reason`, y "
            "`channel` puesto a `customer`."
        ),
        1,
    ),
    (
        "the mutant that survived the first version: the order loses the field and the paragraph "
        "underneath still explains it",
        _enum_step(
            "Cancel it with `appointments.appointments.cancel`: that `appointment_id`, a `reason`, "
            "and `channel` set to `customer`.\n\nAnd that is why the `customer_id` goes with it: "
            "Citas refuses a cancellation that does not say who is asking."
        ),
        1,
    ),
    (
        "the staff channel names nobody on purpose — the agenda screen owns the appointment",
        _enum_step("`appointments.appointments.cancel` with `channel` = `staff`."),
        0,
    ),
    (
        "a command the step never handed over binds nothing here",
        _enum_step(
            "`appointments.appointments.create`, `channel` set to `customer`",
            ("appointments.appointments.create",),
        ),
        0,
    ),
    (
        "a prompt that never orders the channel is not ordering a cancellation either",
        _enum_step("You may call `appointments.appointments.cancel` if she asks for it."),
        0,
    ),
]


# `(label, file name, document, the pins its grants declare, problems expected)` — the unit tests
# of `unpinned_command_problems`. The pins are handed in rather than read off disk so a row can
# describe a sidecar that does not exist: what the rule judges is the PAIR (what the step may call,
# what the grant fixed), and only half of that lives in the document.
_PIN_OK = {CANCEL_COMMAND: {"channel": "customer"}}
_PIN_NONE = {CANCEL_COMMAND: {}}
# …and the same pair for MOVING (whatsapp_inbox#105). Kept apart from `_PIN_OK` so a row can
# describe the half-applied fix this issue is most likely to ship: cancelling narrowed months ago,
# moving added afterwards with the grant left wide.
_PIN_OK_BOTH = {CANCEL_COMMAND: {"channel": "customer"}, MOVE_COMMAND: {"channel": "customer"}}
_PIN_MOVE_WIDE = {CANCEL_COMMAND: {"channel": "customer"}, MOVE_COMMAND: {}}


def _unwatched_canceller(policy="auto"):
    """The step whatsapp_inbox#100 is about: books and cancels, and nobody reads it first."""
    return _ai_step("book_appointment", policy, (BOOKING_COMMAND, CANCEL_COMMAND))


def _mover(policy="auto", sid="book_appointment"):
    """The step whatsapp_inbox#105 adds: it books, cancels AND moves."""
    return _ai_step(sid, policy, (BOOKING_COMMAND, CANCEL_COMMAND, MOVE_COMMAND))


PIN_CASES = [
    (
        "what this module ships after whatsapp_inbox#100: the unwatched writer may cancel, and its "
        "grant says AS THE CUSTOMER",
        UNATTENDED,
        _fixture_doc(_unwatched_canceller()),
        _PIN_OK,
        0,
    ),
    (
        "the red whatsapp_inbox#100 IS: the same permission with nothing fixed, so the salon's own "
        "cancellation rules hang on a paragraph of prompt",
        UNATTENDED,
        _fixture_doc(_unwatched_canceller()),
        _PIN_NONE,
        1,
    ),
    (
        "the pin CONTRADICTED: a grant that fixes the wide value is not a narrower grant, it is the "
        "old one written down",
        UNATTENDED,
        _fixture_doc(_unwatched_canceller()),
        {CANCEL_COMMAND: {"channel": "staff"}},
        1,
    ),
    (
        "a pin on ANOTHER field looks like a pinned grant and fixes nothing that matters: `channel` "
        "is still the model's to choose, and omitting it is still `staff`",
        UNATTENDED,
        _fixture_doc(_unwatched_canceller()),
        {CANCEL_COMMAND: {"reason": "asked by WhatsApp"}},
        1,
    ),
    (
        "the UNNAMED_FAMILY twin owes the pin too (whatsapp_inbox#107): a person approving in the tray is "
        "reading a draft written FOR THE CUSTOMER, not a payload, so the review never shows her "
        "which `channel` the cancellation carries — a review is a workflow control, never a "
        "permission boundary",
        UNNAMED_FAMILY,
        _fixture_doc(_ai_step("propose_appointment", "manual", (BOOKING_COMMAND, CANCEL_COMMAND))),
        _PIN_NONE,
        1,
    ),
    (
        "what this module ships after whatsapp_inbox#107: the same attended writer, and its grant "
        "says AS THE CUSTOMER — which is the declaration this battery can hold it to, not proof "
        "that a hub enforces it (hub#1654) nor that the gallery card copies it (ERPlora/flows#99)",
        UNNAMED_FAMILY,
        _fixture_doc(_ai_step("propose_appointment", "manual", (BOOKING_COMMAND, CANCEL_COMMAND))),
        _PIN_OK,
        0,
    ),
    (
        "a step with NO policy at all is owed the pin like any other: since whatsapp_inbox#107 the "
        "verdict does not depend on who is watching, so a document that forgets to declare its "
        "policy cannot fall through the one hole that reading it would open",
        UNATTENDED,
        _fixture_doc(
            {"id": "book", "kind": "ai", "prompt": "", "tools": {"commands": [CANCEL_COMMAND]}}
        ),
        _PIN_NONE,
        1,
    ),
    (
        "a command the table does not name is not owed a pin: this is a list of the values that "
        "must be narrowed, not a demand that every permission carry one. `customers.create` "
        "carries no argument that widens anything — there is no `channel` on it and no diary it "
        "can reach",
        UNATTENDED,
        _fixture_doc(_ai_step("know_the_customer", "auto", ("customers.create",))),
        {"customers.create": {}},
        0,
    ),
    (
        "🔴 and BOOKING is in the table since whatsapp_inbox#124, with a grant that fixes nothing: "
        "`booked_online` left out makes `born_confirmed` false on EVERY hub, so the salon that "
        "switched «confirm automatically» on still confirms one by one and the recipe tells the "
        "customer she is booked",
        UNATTENDED,
        _fixture_doc(_ai_step("book_appointment", "auto", (BOOKING_COMMAND,))),
        {BOOKING_COMMAND: {}},
        1,
    ),
    (
        "…and the pin really in the grant is the green: the same document, the same command, one "
        "JSON key deep in the sidecar",
        UNATTENDED,
        _fixture_doc(_ai_step("book_appointment", "auto", (BOOKING_COMMAND,))),
        {BOOKING_COMMAND: {"booked_online": True}},
        0,
    ),
    (
        "a pin that CONTRADICTS the table is the same hole wearing the opposite face: `false` is "
        "the schema default, so pinning it is pinning the bug in place",
        UNATTENDED,
        _fixture_doc(_ai_step("book_appointment", "auto", (BOOKING_COMMAND,))),
        {BOOKING_COMMAND: {"booked_online": False}},
        1,
    ),
    (
        "no grant for the command at all: `main()` is already saying that in its own words, and a "
        "second complaint sends the reader looking for a pin on a line that is not there",
        UNATTENDED,
        _fixture_doc(_unwatched_canceller()),
        {},
        0,
    ),
    (
        "a DETERMINISTIC command step is not what the pin is for: `kind: command` takes the payload "
        "the DOCUMENT maps, so there is no model choosing the channel and pinning it would break a "
        "template that legitimately cancels for the salon",
        UNATTENDED,
        _fixture_doc({"id": "drop_it", "kind": "command", "command": CANCEL_COMMAND, "params": {}}),
        _PIN_NONE,
        0,
    ),
    (
        "what this module ships after whatsapp_inbox#105: the unwatched writer may MOVE too, and "
        "both permissions say AS THE CUSTOMER",
        UNATTENDED,
        _fixture_doc(_mover()),
        _PIN_OK_BOTH,
        0,
    ),
    (
        "🔴 the half-applied fix this issue is one edit away from: cancelling was narrowed in "
        "whatsapp_inbox#100 and moving arrives with its grant wide, so `channel` falls back to "
        "`staff` and the move goes out on the salon's own account — no notice window, no maximum "
        "advance, no check of whose appointment it is",
        UNATTENDED,
        _fixture_doc(_mover()),
        _PIN_MOVE_WIDE,
        1,
    ),
    (
        "the move pin CONTRADICTED, which reads like a narrower grant and is the wide one written "
        "down",
        UNATTENDED,
        _fixture_doc(_mover()),
        {CANCEL_COMMAND: {"channel": "customer"}, MOVE_COMMAND: {"channel": "staff"}},
        1,
    ),
    (
        "and the UNNAMED_FAMILY twin owes the move pin on the same grounds as its cancellation one "
        "(whatsapp_inbox#107): what the salon reads in the tray is a draft for the customer, and "
        "no screen there says which `channel` the move will carry",
        UNNAMED_FAMILY,
        _fixture_doc(_mover("manual", "propose_appointment")),
        _PIN_MOVE_WIDE,
        1,
    ),
]


# `(label, file name, document, the pins its grants declare, problems expected)` — the unit tests of
# `unpinned_query_problems`. Handed in for the same reason as `PIN_CASES`: half of what the rule
# judges lives in a sidecar, so a row has to be able to describe one that does not exist.
_RESOLVER = _query_step("resolve_customer", RESOLVER_QUERY, _OWN_PHONE)
_QPIN_OK = {OWNED_APPOINTMENTS_QUERY: {"customer_id": "steps.resolve_customer.id"}}
_QPIN_NONE = {OWNED_APPOINTMENTS_QUERY: {}}


def _diary_reader(policy="auto", sid="book_appointment"):
    """The step whatsapp_inbox#119 is about: a model holding the read that returns a whole diary."""
    return _ai_step(sid, policy, (BOOKING_COMMAND,), queries=(OWNED_APPOINTMENTS_QUERY,))


def _diary_reader_using(resolver, policy="auto", sid="book_appointment"):
    """…and the same step with a prompt that SENDS one resolver's id, as the real ones do."""
    step = _diary_reader(policy, sid)
    step["prompt"] = f"Her id is {{{{steps.{resolver}.id}}}}. Use it and nothing else."
    return step


QUERY_PIN_CASES = [
    (
        "what this module ships after whatsapp_inbox#119: the model may read a diary, and its "
        "grant says WHOSE — the customer the deterministic resolver found from the trusted phone",
        UNATTENDED,
        _fixture_doc(_RESOLVER, _diary_reader()),
        _QPIN_OK,
        0,
    ),
    (
        "\U0001f534 the red whatsapp_inbox#119 IS: the same read granted by name with nothing "
        "fixed, so «one customer, and only that one» is a paragraph of prompt and the model picks "
        "the `customer_id` while it reads a stranger's message",
        UNATTENDED,
        _fixture_doc(_RESOLVER, _diary_reader()),
        _QPIN_NONE,
        1,
    ),
    (
        "the pin aimed at the MODEL's own step instead of the resolver: the id is still whatever "
        "the turn decided it was, which is the hole with one more hop in it",
        UNATTENDED,
        _fixture_doc(_RESOLVER, _diary_reader()),
        {OWNED_APPOINTMENTS_QUERY: {"customer_id": "steps.book_appointment.id"}},
        1,
    ),
    (
        "the pin written as a TEMPLATE: `check_pin_value` refuses `{{…}}` and `PUT …/grants` is "
        "all-or-nothing, so this does not widen the grant — it installs the recipe with no "
        "permissions at all",
        UNATTENDED,
        _fixture_doc(_RESOLVER, _diary_reader()),
        {OWNED_APPOINTMENTS_QUERY: {"customer_id": "{{steps.resolve_customer.id}}"}},
        1,
    ),
    (
        "a pin on ANOTHER field looks like a pinned grant and fixes nothing that matters: whose "
        "diary it is stays the model's to choose",
        UNATTENDED,
        _fixture_doc(_RESOLVER, _diary_reader()),
        {OWNED_APPOINTMENTS_QUERY: {"limit": 20}},
        1,
    ),
    (
        "the UNNAMED_FAMILY twin owes it too: what the salon approves in the tray is a draft for the "
        "customer, and a read never reaches the tray at all — by then the diary has been read",
        UNNAMED_FAMILY,
        _fixture_doc(_RESOLVER, _diary_reader("manual", "propose_appointment")),
        _QPIN_NONE,
        1,
    ),
    (
        "silent when the document has NO resolver: there is no id to pin to, and "
        "`own_customer_only_problems` is already failing on the bigger half",
        UNATTENDED,
        _fixture_doc(_diary_reader()),
        _QPIN_NONE,
        0,
    ),
    (
        "silent when the grant is missing altogether: `main()` compares needed against declared "
        "and says it in its own words",
        UNATTENDED,
        _fixture_doc(_RESOLVER, _diary_reader()),
        {},
        0,
    ),
    (
        "silent on a DETERMINISTIC read of the diary: there the `customer_id` is mapped by the "
        "document, so no model chooses whose it is",
        UNATTENDED,
        _fixture_doc(
            _RESOLVER,
            _query_step("her_diary", OWNED_APPOINTMENTS_QUERY, {"customer_id": "{{steps.resolve_customer.id}}"}),
        ),
        _QPIN_NONE,
        0,
    ),
    (
        "silent on a read this table says nothing about: the rule names the diary, not every query "
        "a model may ever hold",
        UNATTENDED,
        _fixture_doc(_RESOLVER, _ai_step("ask", "auto", (), queries=("services.services.list",))),
        {"services.services.list": {}},
        0,
    ),
    (
        "what the shipped documents really look like — TWO resolvers, and the pin names the one "
        "the step's own prompt sends as the `customer_id`",
        UNATTENDED,
        _fixture_doc(
            _query_step("find_customer", RESOLVER_QUERY, _OWN_PHONE),
            _RESOLVER,
            _diary_reader_using("resolve_customer"),
        ),
        _QPIN_OK,
        0,
    ),
    (
        "\U0001f534 pinned to the OTHER resolver: both are deterministic and both are keyed on the "
        "trusted phone, so this looks narrow — and it denies every run where the customer was "
        "CREATED a step ago, because the earlier read found nobody and the pin resolves to `null`",
        UNATTENDED,
        _fixture_doc(
            _query_step("find_customer", RESOLVER_QUERY, _OWN_PHONE),
            _RESOLVER,
            _diary_reader_using("resolve_customer"),
        ),
        {OWNED_APPOINTMENTS_QUERY: {"customer_id": "steps.find_customer.id"}},
        1,
    ),
    (
        "silent when the only resolver runs AFTER the reader: there is nothing resolved yet to pin "
        "to, and `own_customer_only_problems` owns that red",
        UNATTENDED,
        _fixture_doc(_diary_reader(), _RESOLVER),
        _QPIN_NONE,
        0,
    ),
]


# `(label, file name, document, the families that really ship, problems expected)` — the unit
# tests of `missing_instruction_problems`. The families are handed in for the same reason the pins
# are in `PIN_CASES`: half of what the rule judges is not in the document, and a row has to be able
# to describe a `flows/` folder that does not exist here.
# The healthy tree, read out of the table under test rather than written down a second time:
# a literal copy here silently stopped being «what ships» the day a third recipe was added
# (whatsapp_inbox#125), and then every case below judged the rule against a world of two.
_SHIPPED_FAMILIES = set(PINNED_INSTRUCTIONS)
_RESERVATION_EN = "reservation-from-whatsapp.en.flow.json"
_RESERVATION_ES = "reservation-from-whatsapp.es.flow.json"
_APPOINTMENT_ES = "appointment-from-whatsapp.es.flow.json"


def _saying(*sentences):
    """A document whose one `ai` step says exactly these lines and nothing else."""
    return _fixture_doc(_ai_step("s", "manual", (), "\n".join(sentences)))


# Read out of the table rather than typed here, and that is the point: delete a row and these rows
# stop naming anything, so the table cannot be switched off quietly.
#
# 🪦 The two whatsapp_inbox#70 sentences — the technical reason a booking broke stays with the
# business, and an expired proposal is never explained as nobody having looked — went with the
# attended recipes in whatsapp_inbox#124. They are not lost guards: both endings exist only where a
# write PARKS at a person (`unanswered_ending_problems` gates on the last writing step being
# `policy: manual`), and no document ships that shape any more. If an attended recipe ever comes
# back, its rows come back with it.
_ES_CHANNEL = PINNED_INSTRUCTIONS["appointment-from-whatsapp"][0][1]["es"]
_ES_MOVE_WHO = PINNED_INSTRUCTIONS["appointment-from-whatsapp"][1][1]["es"]
_ES_BOOKED_ONLINE = PINNED_INSTRUCTIONS["appointment-from-whatsapp"][2][1]["es"]
_EN_BLOCKED = PINNED_INSTRUCTIONS["reservation-from-whatsapp"][0][1]["en"]
_EN_ADVANCE = PINNED_INSTRUCTIONS["reservation-from-whatsapp"][1][1]["en"]
_ES_BLOCKED = PINNED_INSTRUCTIONS["reservation-from-whatsapp"][0][1]["es"]
_ES_ADVANCE = PINNED_INSTRUCTIONS["reservation-from-whatsapp"][1][1]["es"]


INSTRUCTION_CASES = [
    (
        "the English document says every pinned instruction",
        _RESERVATION_EN,
        _saying(_EN_BLOCKED, _EN_ADVANCE),
        _SHIPPED_FAMILIES,
        0,
    ),
    (
        "and so does the Spanish one, in Spanish",
        _RESERVATION_ES,
        _saying(_ES_BLOCKED, _ES_ADVANCE),
        _SHIPPED_FAMILIES,
        0,
    ),
    (
        "whatsapp_inbox#112 ITSELF: the Spanish translation lost both instructions and carries the "
        "English ones instead — every other rule here stays green, because they judge what the "
        "document DOES and this is what it SAYS",
        _RESERVATION_ES,
        _saying(_EN_BLOCKED, _EN_ADVANCE),
        _SHIPPED_FAMILIES,
        2,
    ),
    (
        "one of the two lost, which is how it really happens: a translator keeps the paragraph and "
        "drops the sentence at the end of it",
        _RESERVATION_ES,
        _saying(_ES_BLOCKED),
        _SHIPPED_FAMILIES,
        1,
    ),
    (
        "the sentence may live in ANY step of the document: which step holds it is exactly what an "
        "honest rewrite moves around, and a rule that also pinned the step would turn every "
        "rewrite into a red",
        _RESERVATION_EN,
        _fixture_doc(
            _ai_step("first", "manual", (), "nothing to see here"),
            _ai_step("second", "manual", (), "\n".join((_EN_BLOCKED, _EN_ADVANCE))),
        ),
        _SHIPPED_FAMILIES,
        0,
    ),
    (
        "a language this battery has no wording for is a document nobody can be held to: the "
        "translation goes in the table in the same commit that ships the document",
        "reservation-from-whatsapp.fr.flow.json",
        _saying(_EN_BLOCKED, _EN_ADVANCE),
        _SHIPPED_FAMILIES,
        2,
    ),
    (
        "a recipe that SHIPS and lost its row: the other half of the anchoring, and the one that "
        "matters, because a guard you can switch off by deleting a row is not a guard. Measured "
        "in review of whatsapp_inbox#112: dropping the table family from the table and THEN losing "
        "the advance-window sentence from its Spanish document — which is whatsapp_inbox#108 "
        "again, in the half nobody is watching — left this battery green",
        "task-from-whatsapp.en.flow.json",
        _saying("whatever this recipe wants to say"),
        _SHIPPED_FAMILIES | {"task-from-whatsapp"},
        1,
    ),
    (
        "the two recipes that really ship are both in the table, so the rule above costs nothing "
        "on a healthy tree: a red here means a row went missing, never that a recipe is new",
        _RESERVATION_EN,
        _saying(_EN_BLOCKED, _EN_ADVANCE),
        _SHIPPED_FAMILIES,
        0,
    ),
    (
        "the salon family is pinned to its own sentences, and reading them out of the table here "
        "is what makes the table itself tamper-evident: delete the row and this row stops naming "
        "anything",
        _APPOINTMENT_ES,
        _saying(_ES_CHANNEL, _ES_MOVE_WHO, _ES_BOOKED_ONLINE),
        _SHIPPED_FAMILIES,
        0,
    ),
    (
        "and the salon document that lost them both, which is the one that writes with nobody "
        "watching: a model with no sentence telling it why `channel` is `customer` decides on its "
        "own what it means",
        _APPOINTMENT_ES,
        _saying("aquí no se dice nada del `channel`", _ES_BOOKED_ONLINE),
        _SHIPPED_FAMILIES,
        2,
    ),
    (
        "🔴 and the row whatsapp_inbox#105 adds, losable on its own: the Spanish document still "
        "explains the channel it CANCELS with and never says that moving carries it too — which "
        "is exactly the shape whatsapp_inbox#108 had, a paragraph kept and the sentence at the "
        "end of it dropped, in the half nobody reads",
        _APPOINTMENT_ES,
        _saying(_ES_CHANNEL, _ES_BOOKED_ONLINE),
        _SHIPPED_FAMILIES,
        1,
    ),
    (
        "🔴 and the row whatsapp_inbox#124 adds, losable on its own: the Spanish document still "
        "explains both channels and never orders `booked_online`. It is the most losable clause "
        "of the three — it is four words inside a numbered instruction, not a paragraph — and it "
        "is the one whose loss the customer pays for twice: the grant pins the field, so the hub "
        "refuses the call that omits it, and the Spanish half books nothing at all while the "
        "English half keeps working",
        _APPOINTMENT_ES,
        _saying(_ES_CHANNEL, _ES_MOVE_WHO),
        _SHIPPED_FAMILIES,
        1,
    ),
    (
        "a family that is pinned and no longer SHIPS: renaming a recipe leaves the row guarding a "
        "document that does not exist, and every rule here stays green because they only judge the "
        "documents that are there (the hole `shipped_recipe_problems` closes for BOOKING_RULES). "
        "This is not hypothetical here: whatsapp_inbox#124 renamed both families, and this row is "
        "what would have caught the table being left behind",
        _RESERVATION_EN,
        _saying(_EN_BLOCKED, _EN_ADVANCE),
        _SHIPPED_FAMILIES - {"appointment-from-whatsapp"},
        1,
    ),
]


# The floor rule's own mutants. A document that hands MOVE over, one that does not, and the two
# readings of the neighbour's past: the release that already took the fields and the one below it.
_FLOOR_MOVER = {
    "steps": [{"id": "book_appointment", "kind": "ai", "tools": {"commands": [MOVE_COMMAND]}}]
}
_FLOOR_BOOKER = {
    "steps": [
        {
            "id": "book_appointment",
            "kind": "ai",
            "tools": {"commands": ["appointments.appointments.create"]},
        }
    ]
}
_FLOOR_CUSTOMER = {
    "steps": [{"id": "know_the_customer", "kind": "ai", "tools": {"commands": ["customers.create"]}}]
}
_FLOOR_TAKES_BOTH = {
    MOVE_COMMAND: {"appointment_id", "start_datetime", "channel", "customer_id"}
}
_FLOOR_TAKES_NEITHER = {MOVE_COMMAND: {"appointment_id", "start_datetime"}}

CONFIRMED_EVENT = "appointments.appointment.confirmed"


def _woken_by(*events):
    """A document that wakes up on these events, and on nothing else."""
    return {"triggers": [{"kind": "event", "event": e} for e in events], "steps": []}


# What `appointments` DECLARED it emits at each of the two releases that matter here — measured on
# its own history while closing whatsapp_inbox#125, not invented: `f213ade` is
# `chore(release): v1.1.25` and its `module.json` has no `events` key at all, and `f3426cd`
# (v1.1.26) is the first published tree that lists the event, because appointments#40 landed with
# the manifest still reading 1.1.25 and a version's zip is written once.
_EMITS_1_1_25 = {"appointments": set()}
_EMITS_1_1_26 = {
    "appointments": {CONFIRMED_EVENT, "appointments.appointment.cancelled"}
}

FLOOR_TRIGGER_CASES = [
    (
        "the floor already declares the event this family waits on",
        _woken_by(CONFIRMED_EVENT),
        _EMITS_1_1_26,
        0,
    ),
    (
        "🔴 whatsapp_inbox#125 as it was first written: the floor is appointments 1.1.25, whose "
        "published manifest declares no events at all, so the salon presses «Confirmar» and the "
        "trigger matches nothing — the very silence the recipe was written to end",
        _woken_by(CONFIRMED_EVENT),
        _EMITS_1_1_25,
        1,
    ),
    (
        "a floor that declares OTHER events but not this one — «it emits something» is not «it "
        "emits this», and reading the set as a truthy flag would call that green",
        _woken_by(CONFIRMED_EVENT),
        {"appointments": {"appointments.appointment.cancelled"}},
        1,
    ),
    (
        "the event's owner is the core, which no `requires.json` pins a floor for: nothing is "
        "declared about it, so nothing is demanded of it",
        _woken_by("hub.whatsapp.message_received"),
        _EMITS_1_1_25,
        0,
    ),
    (
        "the floor could not be read — `main()` skipped it out loud, and guessing here would be "
        "this rule inventing a floor it never saw",
        _woken_by(CONFIRMED_EVENT),
        {},
        0,
    ),
    (
        "a trigger that is not an event has no owner to hold to a floor",
        {"triggers": [{"kind": "schedule", "cron": "0 9 * * *"}], "steps": []},
        _EMITS_1_1_25,
        0,
    ),
    (
        "two triggers and only one of them below the floor: the sound one must not cover the "
        "other, which is how a rule that stops at the first trigger reads",
        _woken_by("appointments.appointment.cancelled", CONFIRMED_EVENT),
        {"appointments": {"appointments.appointment.cancelled"}},
        1,
    ),
]

FLOOR_CASES = [
    (
        "the floor already takes every field these templates send",
        _FLOOR_MOVER,
        _FLOOR_TAKES_BOTH,
        0,
    ),
    (
        "whatsapp_inbox#105 as the mutant M9 left it: the floor is the release BELOW the one that "
        "started taking `channel` + `customer_id`",
        _FLOOR_MOVER,
        _FLOOR_TAKES_NEITHER,
        2,
    ),
    (
        "no step hands the command over, so this family promises nothing about it",
        _FLOOR_BOOKER,
        _FLOOR_TAKES_NEITHER,
        0,
    ),
    (
        "the schema at the floor could not be read — `main()` skipped it out loud, and guessing "
        "here would be this rule inventing a floor it never saw",
        _FLOOR_MOVER,
        {},
        0,
    ),
    (
        "a command handed over whose payload no table here fills: nothing is promised, so nothing "
        "is demanded of the floor",
        _FLOOR_CUSTOMER,
        {"customers.create": set()},
        0,
    ),
    (
        "🔴 whatsapp_inbox#124 owes the floor the same thing whatsapp_inbox#105 did: `booked_online` "
        "is now SENT with every booking, so a floor that predates the field is a recipe the hub "
        "offers to a copy that answers `invalid_payload` to every booking a customer asks for",
        _FLOOR_BOOKER,
        {"appointments.appointments.create": {"customer_id", "start_datetime"}},
        1,
    ),
    (
        "…and the floor that already takes it is the green, so the row above cannot be one that "
        "fires whatever the floor says",
        _FLOOR_BOOKER,
        {"appointments.appointments.create": {"customer_id", "start_datetime", "booked_online"}},
        0,
    ),
]


def _floor_reading_problems():
    """`schema_at_version` reads a real git history, so `floor_field_problems` is only worth what
    this proves: the release that HAS the fields, the one below it, a version nobody released and a
    directory that is not a checkout at all.

    The trap it pins is the one that costs an hour by hand — `-S` also answers with the commit that
    bumped the version AWAY, and that commit is the NEWEST. A reader that took the first sha would
    read the schema of the release ABOVE every floor and call every floor good, which is the exact
    shape of the bug this whole rule is here to catch.
    """
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        (root / "schemas").mkdir()

        def commit(version, props, message):
            (root / "module.json").write_text(
                json.dumps({"id": "appointments", "version": version}, indent=2)
            )
            (root / "schemas" / "reschedule.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {p: {"type": "string"} for p in props},
                    }
                )
            )
            for args in (
                ["add", "-A"],
                ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
                 "commit", "-q", "-m", message],
            ):
                done = subprocess.run(
                    ["git", "-C", str(root)] + args, capture_output=True, text=True
                )
                if done.returncode != 0:
                    problems.append(
                        f"the battery could not build its own git fixture (`git {args[0]}`): "
                        f"{done.stderr.strip()} — `schema_at_version` was NOT proved"
                    )
                    return False
            return True

        done = subprocess.run(
            ["git", "-C", str(root), "init", "-q"], capture_output=True, text=True
        )
        if done.returncode != 0:
            return [
                f"the battery could not build its own git fixture (`git init`): "
                f"{done.stderr.strip()} — `schema_at_version` was NOT proved"
            ]
        # Two releases, the shape `appointments` really has: the fields land in the SECOND one.
        if not commit("1.1.72", ["appointment_id", "start_datetime"], "chore(release): v1.1.72"):
            return problems
        if not commit(
            "1.1.73",
            ["appointment_id", "start_datetime", "channel", "customer_id"],
            "chore(release): v1.1.73",
        ):
            return problems

        rel = "schemas/reschedule.json"
        for label, version, want in [
            (
                "the floor that predates the fields — and the newest commit `-S` answers with is "
                "the one that bumped this version AWAY, so a reader taking the first sha reads "
                "1.1.73 here and never sees the hole",
                "1.1.72",
                {"appointment_id", "start_datetime"},
            ),
            (
                "the release that introduced them",
                "1.1.73",
                {"appointment_id", "start_datetime", "channel", "customer_id"},
            ),
        ]:
            got, why = schema_at_version(root, version, rel)
            if got != want:
                problems.append(
                    f"the battery's own reading of a released schema is wrong — {label}: expected "
                    f"{sorted(want)}, got {got if got is None else sorted(got)} ({why})"
                )

        got, why = schema_at_version(root, "9.9.9", rel)
        if got is not None or not why:
            problems.append(
                f"the battery reads a version nobody released as an answer instead of a skip: "
                f"got {got} ({why}) — a floor typo would then be a silent green"
            )
        got, why = schema_at_version(root, "1.1.73", "schemas/nowhere.json")
        if got is not None or not why:
            problems.append(
                f"the battery reads a schema absent from the release as an answer instead of a "
                f"skip: got {got} ({why})"
            )

        # …and the collector on top of it, because the SKIP is the half that can go quiet. A floor
        # whose past could not be read has to be NAMED: dropping the command from `props` alone
        # makes `floor_field_problems` say nothing about it, and «I could not look» would then
        # read exactly like «the floor is high enough» (measured: that mutant survived).
        commands_def = {MOVE_COMMAND: (root, {"schema": rel})}
        resolved = {"appointments": (root, {"id": "appointments"})}
        for label, floors, want_props, want_skips in [
            (
                "the floor that takes everything these templates send",
                {"appointments": "1.1.73"},
                {MOVE_COMMAND: {"appointment_id", "start_datetime", "channel", "customer_id"}},
                0,
            ),
            (
                "a floor no release ever carried — a typo in `requires.json`",
                {"appointments": "9.9.9"},
                {},
                1,
            ),
            (
                "the family pins no floor for that module, so there is nothing to read it against",
                {},
                {},
                0,
            ),
        ]:
            got_props, got_skips = floor_payload_properties(floors, commands_def, resolved)
            if got_props != want_props or len(got_skips) != want_skips:
                problems.append(
                    f"the battery's own collection of floor payloads is wrong — {label}: expected "
                    f"{want_props} and {want_skips} skip(s), got {got_props} and {got_skips}"
                )

    with tempfile.TemporaryDirectory() as bare:
        got, why = schema_at_version(pathlib.Path(bare), "1.1.73", rel)
        if got is not None or not why:
            problems.append(
                f"the battery reads a directory that is not a git checkout as an answer instead "
                f"of a skip: got {got} ({why}) — on a CI runner with no neighbours that is a "
                f"green over nothing"
            )
    return problems


def _floor_read_reading_problems():
    """`sql_names_at_version` reads a real git history, so `floor_read_column_problems` is only
    worth what this proves: the release that answers the labels, the one below it — whose SQL
    already NAMES them in a comment, the way a release note does — a version nobody released, a
    file absent from the release, and the collector naming every floor it could not read.
    """
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        (root / "queries").mkdir()

        def run(*args):
            done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
            if done.returncode != 0:
                problems.append(
                    f"the battery could not build its own git fixture (`git {args[0]}`): "
                    f"{done.stderr.strip()} — `sql_names_at_version` was NOT proved"
                )
            return done.returncode == 0

        rel = "queries/appointment_get.sql"

        def commit(version, sql, declared=rel):
            queries = {} if declared is None else {APPOINTMENT_READ: {"sql": declared}}
            (root / "module.json").write_text(
                json.dumps({"id": "appointments", "version": version, "queries": queries})
            )
            if sql is not None:
                (root / "queries" / "appointment_get.sql").write_text(sql)
            return run("add", "-A") and run(
                "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
                "commit", "-q", "-m", f"chore(release): v{version}",
            )

        if not run("init", "-q"):
            return problems
        # whatsapp_inbox#173: the release BEFORE the query existed at all — its manifest does not
        # declare it and its tree carries no SQL for it.
        if not commit("1.1.75", None, declared=None):
            return problems
        if not commit(
            "1.1.76",
            "-- start_date_label / start_time_label: coming in appointments#151\n"
            "/* start_time_label */ SELECT a.customer_phone, a.start_datetime FROM a",
        ):
            return problems
        if not commit(
            "1.1.77",
            "SELECT a.customer_phone, a.start_datetime, w.hh AS start_time_label, "
            "w.d AS start_date_label FROM a",
        ):
            return problems
        # …and a release whose manifest declares the query over a file its tree does not carry:
        # that zip answers the read with nothing either.
        if not commit(
            "1.1.78",
            "SELECT a.customer_phone FROM a",
            declared="queries/nowhere.sql",
        ):
            return problems

        for label, version, present, absent in [
            (
                "the release below the labels — they are only in its COMMENTS, and a reader that "
                "kept comments would call this floor good",
                "1.1.76",
                {"customer_phone", "start_datetime"},
                {WHEN_DATE, WHEN_TIME},
            ),
            ("the release that answers them", "1.1.77", {WHEN_DATE, WHEN_TIME}, set()),
        ]:
            got, why = sql_names_at_version(root, version, APPOINTMENT_READ)
            if got is None or got is ABSENT_AT_FLOOR or not present <= got or absent & got:
                problems.append(
                    f"the battery's own reading of a released query is wrong — {label}: wanted "
                    f"{sorted(present)} in and {sorted(absent)} out, got "
                    f"{got if got is None else sorted(got)} ({why})"
                )
        got, why = sql_names_at_version(root, "9.9.9", APPOINTMENT_READ)
        if got is not None or not why:
            problems.append(
                f"the battery reads a version nobody released — a typo in `requires.json` — as an "
                f"answer instead of a skip: got {got} ({why})"
            )
        # 🔴 whatsapp_inbox#173: «the query is not there at the floor» is an ANSWER, and the
        # opposite one from «I could not look». Read as a skip, lowering `customers` to 2.3.44 in a
        # `requires.json` left the battery green while the hub offered the recipe to copies where
        # `customers.by_phone` does not exist — every message failing, nobody answered.
        for label, version in [
            ("the release before the query existed — its manifest does not declare it", "1.1.75"),
            ("a release that declares the query over a SQL file its tree does not carry", "1.1.78"),
        ]:
            got, why = sql_names_at_version(root, version, APPOINTMENT_READ)
            if got is not ABSENT_AT_FLOOR or why:
                problems.append(
                    f"the battery reads {label} as something other than «absent at the floor»: "
                    f"got {got} ({why}) — a floor below the query stays green"
                )

        definitions = {APPOINTMENT_READ: (root, {"sql": rel})}
        resolved = {"appointments": (root, {"id": "appointments"})}
        for label, floors, want, want_skips in [
            ("the floor that answers the labels", {"appointments": "1.1.77"}, True, 0),
            ("a floor no release ever carried", {"appointments": "9.9.9"}, False, 1),
            ("the family pins no floor for that module", {}, False, 0),
            (
                "🔴 a floor that predates the query — an ANSWER («absent»), never a skip",
                {"appointments": "1.1.75"},
                ABSENT_AT_FLOOR,
                0,
            ),
        ]:
            got, skips = floor_read_columns(floors, definitions, resolved, {APPOINTMENT_READ})
            reading = (
                got.get(APPOINTMENT_READ) is ABSENT_AT_FLOOR
                if want is ABSENT_AT_FLOOR
                else (APPOINTMENT_READ in got and got[APPOINTMENT_READ] is not ABSENT_AT_FLOOR)
            )
            if reading != bool(want) or len(skips) != want_skips:
                problems.append(
                    f"the battery's own collection of floor reads is wrong — {label}: expected "
                    f"{'a reading' if want else 'none'} and {want_skips} skip(s), got "
                    f"{sorted(got)} and {skips}"
                )
    return problems


def _identity_reading_problems():
    """`payload_properties` reads the real schema files, so `identity_field_problems` is only worth
    what this proves: a schema on disk, one whose file is missing, one with no `schema` at all."""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        (root / "schemas").mkdir()
        (root / "schemas" / "cancel.json").write_text(
            json.dumps({
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string"},
                    "channel": {"type": "string"},
                    "customer_id": {"type": "string"},
                },
            })
        )
        got = payload_properties({
            "appointments.appointments.cancel": (root, {"schema": "schemas/cancel.json"}),
            "appointments.appointments.create": (root, {"schema": "schemas/missing.json"}),
            "customers.list": (root, {}),
        })
        problems = []
        want = {"appointments.appointments.cancel": {"appointment_id", "channel", "customer_id"}}
        if got != want:
            problems.append(
                f"the battery's own reading of payload properties is wrong: expected {want}, got {got}"
            )
    # …and the anchor itself: the real table against a schema that HAS the pair, against one that
    # lost it (the shape `appointments` dropping `customer_id` would take), and against a workspace
    # whose schema could not be read — which stays quiet, because layer 1b already said so.
    _CHANNEL_ENUM = {"appointments.appointments.cancel": {"channel": ["staff", "customer"]}}
    for label, props, enums, expected in [
        ("the schema declares both fields and the pinned value", want, _CHANNEL_ENUM, 0),
        (
            "`customer_id` is gone from the schema",
            {"appointments.appointments.cancel": {"appointment_id", "channel"}},
            _CHANNEL_ENUM,
            1,
        ),
        ("the command's schema could not be read", {}, {}, 0),
        (
            "`channel` itself is gone: the grant would pin a field the command does not take, and "
            "a pin is applied BEFORE the schema — every cancellation refused, nothing red",
            {"appointments.appointments.cancel": {"appointment_id", "customer_id"}},
            {},
            2,
        ),
        (
            "`customer` is no longer one of the values `channel` accepts: the pin stops being "
            "narrower and becomes never",
            want,
            {"appointments.appointments.cancel": {"channel": ["staff", "client"]}},
            1,
        ),
        (
            "the property has no enum to read: nothing to say about the value, and saying it "
            "anyway would be this rule inventing a contract",
            want,
            {},
            0,
        ),
    ]:
        got_anchor = identity_field_problems("(self-check)", {}, props, enums)
        if len(got_anchor) != expected:
            problems.append(
                f"the battery's own identity anchor is wrong — {label}: expected {expected} "
                f"problem(s), got {len(got_anchor)}: {got_anchor}"
            )
    return problems


def _enum_reading_problems():
    """`payload_enums` reads the real schema file, so `enum_value_problems` is only worth what this
    proves: a schema on disk with one enum field, one whose file is missing, one with no schema."""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        (root / "schemas").mkdir()
        (root / "schemas" / "cancel.json").write_text(
            json.dumps({
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string"},
                    "channel": {"type": "string", "enum": ["staff", "customer"]},
                },
            })
        )
        got = payload_enums({
            "appointments.appointments.cancel": (root, {"schema": "schemas/cancel.json"}),
            "appointments.appointments.create": (root, {"schema": "schemas/missing.json"}),
            "customers.list": (root, {}),
        })
    want = {"appointments.appointments.cancel": {"channel": ["staff", "customer"]}}
    if got != want:
        return [f"the battery's own reading of payload enums is wrong: expected {want}, got {got}"]
    return []


# ── the mutants of «que la toque, no que la escriba» (whatsapp_inbox#101) ─────────────────────

# The trigger that waits for a TAP, as these templates ship it. Disjoint from `LIVE_INBOUND` by
# construction and not by luck: one demands words, the other demands their absence, so no message
# can satisfy both however the core fills `reply_id`.
TAP_TRIGGER = {
    "event.text": {"eq": ""},
    "event.reply_id": {"neq": ""},
    "event.direction": {"neq": "outbound"},
    "event.source": {"neq": "history"},
}
_TAP_PROMPT = f"find the free slots. {TAP_WORDS['en']} `flow_answer`."


def _tap_doc(
    *,
    output=("options",),
    policy="auto",
    commands=("appointments.appointments.create",),
    guard=True,
    rows="steps.pick.slots",
    triggers=("words", "tap"),
    tap_filter=None,
    tap_input=("from", "text", "reply_id"),
    prompt=_TAP_PROMPT,
    extra_copy=None,
):
    """A document that offers the customer rows to tap, with one screw loosened at a time."""
    producer = {"id": "pick", "kind": "ai", "prompt": prompt, "policy": policy}
    if commands:
        producer["tools"] = {"commands": list(commands)}
    if output:
        producer["output"] = {
            "slots": {"type": output[0], "describe": "the free slots you found"}
        }
    steps = [producer]
    if guard:
        steps.append({"id": "any", "kind": "condition", "when": {rows: {"neq": []}}})
    offer = {
        "id": "offer",
        "kind": "notify",
        "channel": "whatsapp",
        "template": "",
        "interactive": {
            "type": "list",
            "body": {"text": "pick one"},
            "action": {"button": "See", "sections": [{"title": "Free", "rows": rows}]},
        },
    }
    if extra_copy:
        offer["vars"] = extra_copy
    steps.append(offer)
    built = []
    if "words" in triggers:
        built.append(
            {
                "kind": "event",
                "event": WHATSAPP_EVENT,
                "filter": LIVE_INBOUND,
                "input": {"from": "event.from", "text": "event.text"},
            }
        )
    if "tap" in triggers:
        built.append(
            {
                "kind": "event",
                "event": WHATSAPP_EVENT,
                "filter": tap_filter or TAP_TRIGGER,
                "input": {
                    key: f"event.{ {'text': 'reply_title'}.get(key, key) }"
                    for key in tap_input
                },
            }
        )
    return {"schema_version": 1, "triggers": built, "steps": steps}


# `(label, file name, document, problems expected)`
TAPPABLE_CASES = [
    (
        "\U0001f534 the tap trigger written with `exists`, which reads right and is not: the core "
        "serves `reply_id` EMPTY and never absent, so it is true for a photo with no caption too "
        "and the booking recipe runs over an empty message",
        UNNAMED_FAMILY,
        _tap_doc(
            tap_filter={
                "event.text": {"eq": ""},
                "event.reply_id": {"exists": True},
                "event.direction": {"neq": "outbound"},
                "event.source": {"neq": "history"},
            }
        ),
        1,
    ),
    (
        "the trigger as it ships tells the two apart: `neq \"\"` wakes up for the tap and leaves "
        "the photo alone",
        UNNAMED_FAMILY,
        _tap_doc(),
        0,
    ),
    (
        "the shape this issue ships: the slots the turn found become the rows she taps, guarded "
        "against the empty list, with a trigger that wakes up for the tap",
        UNNAMED_FAMILY,
        _tap_doc(),
        0,
    ),
    (
        "the recipe as it was: it books unattended, and offers nothing to tap — she types the "
        "sentence back",
        UNATTENDED,
        {
            "schema_version": 1,
            "triggers": [
                {
                    "kind": "event",
                    "event": WHATSAPP_EVENT,
                    "filter": LIVE_INBOUND,
                    "input": {"from": "event.from", "text": "event.text"},
                }
            ],
            "steps": [
                {
                    "id": "pick",
                    "kind": "ai",
                    "prompt": "book it",
                    "policy": "auto",
                    "tools": {"commands": ["appointments.appointments.create"]},
                },
                _notify_step(),
            ],
        },
        1,
    ),
    (
        "🔴 rows from a step that never declared them: `null` reaches Meta as the rows of the list",
        UNNAMED_FAMILY,
        _tap_doc(output=()),
        1,
    ),
    (
        "🔴 declared, but as text: `options` is Meta's row shape and nothing else fits in a list",
        UNNAMED_FAMILY,
        _tap_doc(output=("text",)),
        1,
    ),
    (
        "🔴 nothing refuses the empty list: the turn booked, `slots` is `[]`, and the send fails "
        "after she was already answered",
        UNNAMED_FAMILY,
        _tap_doc(guard=False),
        1,
    ),
    (
        "🔴 the guard is `exists`, which is true for `[]` — the mutant that reads right",
        UNNAMED_FAMILY,
        {
            **_tap_doc(guard=False),
            "steps": [
                _tap_doc(guard=False)["steps"][0],
                {"id": "any", "kind": "condition", "when": {"steps.pick.slots": {"exists": True}}},
                _tap_doc(guard=False)["steps"][1],
            ],
        },
        1,
    ),
    (
        "🔴 no trigger wakes up for the tap: she taps, and nothing happens ever",
        UNNAMED_FAMILY,
        _tap_doc(triggers=("words",)),
        1,
    ),
    (
        "🔴 the tap wakes something up but `reply_id` never reaches the run: it knows somebody "
        "tapped and not which row — the ambiguity this change exists to remove",
        UNNAMED_FAMILY,
        _tap_doc(tap_input=("from", "text")),
        1,
    ),
    (
        "🔴 the prompt stopped promising the words: a turn that ends on a tool call can carry "
        "none, and the confirmation goes out empty",
        UNNAMED_FAMILY,
        _tap_doc(prompt="find the free slots."),
        1,
    ),
    (
        "🔴 `interactive` next to copy of its own: one message, two types — the hub refuses it",
        UNNAMED_FAMILY,
        _tap_doc(extra_copy={"text": "and this"}),
        1,
    ),
    (
        "🔴 the UNNAMED_FAMILY family books too and owes her the same list: the salon that chose to "
        "review before confirming used to get the WORSE experience, which is backwards "
        "(whatsapp_inbox#109). Its slots come from the step that writes the message, never from "
        "the one that proposes — that one can never declare `output`",
        UNNAMED_FAMILY,
        {
            "schema_version": 1,
            "triggers": [
                {
                    "kind": "event",
                    "event": WHATSAPP_EVENT,
                    "filter": LIVE_INBOUND,
                    "input": {"from": "event.from", "text": "event.text"},
                }
            ],
            "steps": [
                {
                    "id": "pick",
                    "kind": "ai",
                    "prompt": "book it",
                    "policy": "manual",
                    "tools": {"commands": ["appointments.appointments.create"]},
                },
                _notify_step(),
            ],
        },
        1,
    ),
    (
        "a family that offers nothing and books nothing is not this rule's business",
        UNNAMED_FAMILY,
        _wa_doc(LIVE_INBOUND),
        0,
    ),
]


# `(label, file name, document, problems expected)` — the producer of the rows, judged by what its
# commands DO. The row above it in `TAPPABLE_CASES` proves the wiring; these prove the FINISHING.
PARKING_CASES = [
    (
        "🔴 the producer may propose a WRITE: the kernel refuses it, `flow_answer` is never called "
        "and the rows leave for Meta as `null`",
        UNNAMED_FAMILY,
        _tap_doc(policy="manual"),
        1,
    ),
    (
        "a `manual` producer whose commands only ANSWER can always finish (hub#1595), which is the "
        "only shape the attended family has: the step that books can never publish the slots",
        UNNAMED_FAMILY,
        _tap_doc(policy="manual", commands=("appointments.availability.slots",)),
        0,
    ),
    (
        "a `manual` producer with no commands at all has nothing to park either",
        UNNAMED_FAMILY,
        _tap_doc(policy="manual", commands=()),
        0,
    ),
    (
        "…and `auto` never parks, whatever it declares: it runs the write in the turn",
        UNNAMED_FAMILY,
        _tap_doc(policy="auto"),
        0,
    ),
    (
        "🔴 the same dead end with NOBODY sending its rows: a `manual` step that owes data "
        "cannot park its write and cannot run it either, so the booking never happens at all. "
        "Declaring `output` is exactly what takes it out of `writing_ai_steps`, so no rule above "
        "looks at it any more and the only thing left is this one (whatsapp_inbox#109)",
        UNNAMED_FAMILY,
        _fixture_doc(
            {
                "id": "book",
                "kind": "ai",
                "policy": "manual",
                "prompt": "propose `appointments.appointments.create` for her",
                "tools": {"commands": ["appointments.appointments.create"]},
                "output": {"picked": {"type": "text", "describe": "what she picked"}},
            }
        ),
        1,
    ),
]


def booking_tables_disagreement_problems():
    """`BOOKING_RULES`, `BIRTH_STATUS_SOURCE` and `BIRTH_STATUS_RULES` name the SAME bookings.

    whatsapp_inbox#124, measured in review. `BOOKING_RULES` is the table `shipped_recipe_problems`
    anchors to what really ships, both ways — a row nobody hands is a red, a booking two families
    hand is a red. The two birth-status tables had no such anchor of their own: a row in
    `BIRTH_STATUS_RULES` for a booking no recipe hands (`orders.orders.create`, say) left the whole
    battery at `EXIT=0`, because `birth_status_problems` only ever judges the documents that
    exist. And the mirror only failed by accident — dropping the table booking from
    `BIRTH_STATUS_RULES` died on a `KeyError` in this file's own fixtures, not on a rule that says
    what went missing. So the three tables are held to one another here, and through
    `BOOKING_RULES` to `flows/`: every booking has its hour rule, its read and its two endings, in
    the same languages, or none of them.
    """
    problems = []
    for label, table in (
        ("BIRTH_STATUS_SOURCE", BIRTH_STATUS_SOURCE),
        ("BIRTH_STATUS_RULES", BIRTH_STATUS_RULES),
    ):
        for booking in sorted(set(table) - set(BOOKING_RULES)):
            problems.append(
                f"`{label}` has a row for `{booking}` and `BOOKING_RULES` does not: nothing "
                f"anchors that row to a recipe that ships, so it guards nothing and reads as if "
                f"it did. Give the booking its hour rule too, or take the row out"
            )
        for booking in sorted(set(BOOKING_RULES) - set(table)):
            problems.append(
                f"`BOOKING_RULES` names `{booking}` and `{label}` has no row for it: the recipe "
                f"that books with it ships with an hour rule and no way to tell the customer "
                f"what really happened to the booking, which is whatsapp_inbox#124 all over again"
            )
    for booking in sorted(set(BOOKING_RULES) & set(BIRTH_STATUS_RULES)):
        languages, endings = (
            set(BOOKING_RULES[booking]),
            set(BIRTH_STATUS_RULES[booking]),
        )
        if languages != endings:
            problems.append(
                f"`{booking}` has its hour rule in {sorted(languages)} and its birth-status "
                f"wording in {sorted(endings)}: a language with one and not the other ships a "
                f"document this battery can only half vouch for"
            )
    return problems


_TRIGGER_FAMILIES = set(FAMILY_TRIGGERS)
_CONFIRMED_DOC = "appointment-confirmed-to-whatsapp.en.flow.json"


def _waiting(*events):
    """A document that wakes up for exactly these events, and carries nothing else."""
    return {"triggers": [{"kind": "event", "event": e} for e in events], "steps": []}


TRIGGER_CASES = [
    (
        "the family waits on what its row says, which is the healthy tree",
        _CONFIRMED_DOC,
        _waiting(CONFIRMATION_TRIGGER),
        _TRIGGER_FAMILIES,
        0,
    ),
    (
        "🔴 the document was repointed at another event and kept its file name: it still installs, "
        "the card still reads «on», and it now runs at a moment nobody designed it for — spending "
        "the same grants over data that means something else",
        _CONFIRMED_DOC,
        _waiting("appointments.appointment.cancelled"),
        _TRIGGER_FAMILIES,
        1,
    ),
    (
        "🔴 and the shape a merge leaves behind: the right event AND another one. Every rule that "
        "reads the trigger is happy, because the one it wanted is in there — and the recipe fires "
        "TWICE, so the customer is told her appointment was confirmed when it was cancelled",
        _CONFIRMED_DOC,
        _waiting(CONFIRMATION_TRIGGER, "appointments.appointment.updated"),
        _TRIGGER_FAMILIES,
        1,
    ),
    (
        "🔴 no trigger at all: the document saves, the card turns on and nothing ever wakes it. "
        "That is the silence of whatsapp_inbox#125 with a green battery over it",
        _CONFIRMED_DOC,
        _waiting(),
        _TRIGGER_FAMILIES,
        1,
    ),
    (
        "🔴 a family SHIPS and the table does not name it: nothing says what that recipe may wake "
        "up for, which is the blanket check being deleted one family at a time",
        _CONFIRMED_DOC,
        _waiting(CONFIRMATION_TRIGGER),
        _TRIGGER_FAMILIES | {"order-from-whatsapp"},
        1,
    ),
    (
        "🔴 and the mirror a rename leaves: a row pointing at a family nothing ships, guarding "
        "nothing while reading as if it did",
        _CONFIRMED_DOC,
        _waiting(CONFIRMATION_TRIGGER),
        _TRIGGER_FAMILIES - {"reservation-from-whatsapp"},
        1,
    ),
]


def _confirmation(
    read=True,
    read_id="read_appointment",
    appointment_id=CONFIRMED_ID,
    guard=True,
    found_guard=True,
    notify=True,
    notify_to=None,
    text=None,
):
    """The whatsapp_inbox#125 recipe, with one screw loosened at a time."""
    phone = f"steps.{read_id}.{DIARY_PHONE}"
    if text is None:
        text = (
            f"Confirmed! See you on {{{{steps.{read_id}.{WHEN_DATE}}}}} at "
            f"{{{{steps.{read_id}.{WHEN_TIME}}}}}."
        )
    steps = []
    if read:
        steps.append(
            {
                "id": read_id,
                "kind": "query",
                "query": APPOINTMENT_READ,
                "params": {"appointment_id": appointment_id},
                "result": "first",
                "limit": 1,
            }
        )
    steps.append(
        {
            "id": "reachable_on_whatsapp",
            "kind": "query",
            "query": CONVERSATIONS_READ,
            "params": {PHONE_FILTER: phone},
            "result": "first",
            "limit": 1,
        }
    )
    when = {"steps.reachable_on_whatsapp.found": {"eq": True}}
    if guard:
        when[phone] = {"neq": ""}
    if read and found_guard:
        when[f"steps.{read_id}.{READ_FOUND}"] = {"eq": True}
    steps.append({"id": "has_a_thread", "kind": "condition", "when": when})
    if notify:
        steps.append(
            {
                "id": "tell_the_customer",
                "kind": "notify",
                "channel": "whatsapp",
                "to": {
                    "query": CONVERSATIONS_READ,
                    "params": {PHONE_FILTER: notify_to or phone},
                    "field": "contact_phone",
                },
                "template": "",
                "vars": {"text": text},
            }
        )
    return {
        "schema_version": 1,
        "triggers": [
            {
                "kind": "event",
                "event": CONFIRMATION_TRIGGER,
                "input": {"appointment_id": "event.appointment_id"},
            }
        ],
        "steps": steps,
    }


CONFIRMATION_CASES = [
    (
        "the salon confirms, the diary is read and she is told on the number it holds",
        _CONFIRMED_DOC,
        _confirmation(),
        0,
    ),
    (
        "a family that waits on an incoming message is not this rule's business: judging it would "
        "report every WhatsApp recipe for not reading a diary it has no reason to read",
        "appointment-from-whatsapp.en.flow.json",
        {"triggers": [{"kind": "event", "event": WHATSAPP_EVENT}], "steps": []},
        0,
    ),
    (
        "🔴 whatsapp_inbox#125 word for word: it wakes up when the salon confirms and sends "
        "NOTHING. She asked on WhatsApp, was told the salon would confirm shortly, the salon "
        "confirmed — and the chat stayed quiet, with the card reading «on»",
        _CONFIRMED_DOC,
        _confirmation(notify=False),
        1,
    ),
    (
        "🔴 the guard that keeps an EMPTY phone out of the lookup is gone, leaving `found` on its "
        "own. `contact_phone` is `op: like`, so a walk-in booked over the counter with no number "
        "on her card goes out as `%%`, matches every conversation in the inbox and answers "
        "`found: true`: the confirmation is delivered to a stranger, or the run dies with "
        "`flow.recipient_ambiguous` and nobody can read why",
        _CONFIRMED_DOC,
        _confirmation(found_guard=False),
        1,
    ),
    (
        "🔴 the same `%%`, reached by `null`: nothing demands that the diary read FOUND the "
        "appointment. Deleted between the confirmation and the run — the outbox delivers "
        "at-least-once — the read answers with no fields, the `neq: \"\"` above is TRUE over a "
        "`null`, and the phone travels as `null`, which the list engine reads as NO FILTER AT ALL",
        _CONFIRMED_DOC,
        _confirmation(guard=False),
        1,
    ),
    (
        "🔴 the message is addressed by the conversation's OWN answer instead of by the diary: "
        "circular, and it picks whoever the lookup happened to find first",
        _CONFIRMED_DOC,
        _confirmation(notify_to="steps.reachable_on_whatsapp.contact_phone"),
        1,
    ),
    (
        "🔴 the diary is never read: the event carries `appointment_id` and nothing else, so there "
        "is no phone, no service and no professional in this run — nothing to write with, and "
        "nowhere to write it (two marks, because the notify is then keyed on a value no step "
        "produces)",
        _CONFIRMED_DOC,
        _confirmation(read=False),
        2,
    ),
    (
        "🔴 the diary is read for an appointment the event did not name: another customer's hour, "
        "professional and phone number, read out to whoever this run reaches",
        _CONFIRMED_DOC,
        _confirmation(appointment_id="input.customer_id"),
        1,
    ),
    (
        "🔴 whatsapp_inbox#146 word for word: «Confirmed! See you for your Cut with Ana». She just "
        "asked for an appointment and the one thing she needs to know — WHEN to come — is the one "
        "thing the message leaves out",
        _CONFIRMED_DOC,
        _confirmation(
            text="Confirmed! See you for your {{steps.read_appointment.service_name}} with "
            "{{steps.read_appointment.staff_name}}."
        ),
        1,
    ),
    (
        "🔴 the day without the hour: «see you on Tuesday» leaves her guessing the half she needs "
        "to set an alarm by",
        _CONFIRMED_DOC,
        _confirmation(text="Confirmed! See you on {{steps.read_appointment.start_date_label}}."),
        1,
    ),
    (
        "🔴 the hour without the day: «see you at 10:30» — which 10:30, when she asked for two "
        "slots or the salon moved her",
        _CONFIRMED_DOC,
        _confirmation(text="Confirmed! See you at {{steps.read_appointment.start_time_label}}."),
        1,
    ),
    (
        "🔴 the raw instant instead of the labels: `2026-09-15T10:30:00+02:00` reaches her phone "
        "as it is, because the mapping language has no clock and no formatter",
        _CONFIRMED_DOC,
        _confirmation(text="Confirmed! See you at {{steps.read_appointment.start_datetime}}."),
        1,
    ),
    (
        "🔴 the right field names, read off a step that is NOT the appointment read — it resolves "
        "to nothing and the customer gets an empty «see you on  at .»",
        _CONFIRMED_DOC,
        _confirmation(
            text="See you on {{steps.reachable_on_whatsapp.start_date_label}} at "
            "{{steps.reachable_on_whatsapp.start_time_label}}."
        ),
        1,
    ),
    (
        "🔴 the labels written bare, without the braces: the kernel only substitutes `{{…}}`, so "
        "she receives the literal words `steps.read_appointment.start_date_label`",
        _CONFIRMED_DOC,
        _confirmation(
            text="See you on steps.read_appointment.start_date_label at "
            "steps.read_appointment.start_time_label."
        ),
        1,
    ),
]


# What `appointments.appointments.get` NAMED in its published SQL on each side of appointments#151 —
# the release that started answering the day and the hour already readable is 1.1.77 (`2cd6d26`),
# and 1.1.76 (`52588bf`) is the one below it. Trimmed to the names this family reads.
_READS_1_1_76 = {APPOINTMENT_READ: {"customer_phone", "service_name", "staff_name", "start_datetime"}}
_READS_1_1_77 = {
    APPOINTMENT_READ: _READS_1_1_76[APPOINTMENT_READ] | {WHEN_DATE, WHEN_TIME}
}

def _read_only_in_a_condition_key():
    """The confirmation recipe with one more guard, on a column the fixture floors never answer."""
    doc = _confirmation()
    doc["steps"].insert(
        1,
        {
            "id": "still_booked",
            "kind": "condition",
            "when": {"steps.read_appointment.status": {"eq": "confirmed"}},
        },
    )
    return doc


FLOOR_READ_CASES = [
    (
        "the floor already answers every column the recipe reads — `found`/`count` are the "
        "kernel's contract keys (`flows/query.rs`), never a column, and must not be demanded",
        _confirmation(),
        _READS_1_1_77,
        0,
    ),
    (
        "🔴 whatsapp_inbox#146 with the text changed and the floor left at 1.1.76: the hub OFFERS "
        "the recipe to a copy whose read has no labels, and the customer receives the literal "
        "`{{steps.read_appointment.start_date_label}}` — worse than not saying the hour (two "
        "columns, two problems)",
        _confirmation(),
        _READS_1_1_76,
        2,
    ),
    (
        "🔴 a column read in a CONDITION and in a param: the phone guard and the lookup read "
        "`customer_phone`, and a floor that predates it turns both into a `null` check",
        _confirmation(),
        {APPOINTMENT_READ: _READS_1_1_77[APPOINTMENT_READ] - {"customer_phone"}},
        1,
    ),
    (
        "🔴 a column read ONLY as a condition KEY — the shape `when` spells its operands in — and "
        "nowhere else: a walker that only reads values never sees it",
        _read_only_in_a_condition_key(),
        _READS_1_1_77,
        1,
    ),
    (
        "the query's floor could not be read — `main()` skipped it out loud, and guessing here "
        "would be this rule inventing a floor it never saw",
        _confirmation(),
        {},
        0,
    ),
    (
        "a read of this module's OWN query is pinned by no neighbour's floor: nothing is "
        "promised about it, so nothing is demanded (`reachable_on_whatsapp.contact_phone`)",
        _confirmation(),
        {CONVERSATIONS_READ: set()} | _READS_1_1_77,
        0,
    ),
    (
        "🔴 whatsapp_inbox#173: the query itself does not exist at the declared floor — one "
        "problem for the step that reads it, however many of its columns the recipe uses",
        _confirmation(),
        {APPOINTMENT_READ: ABSENT_AT_FLOOR},
        1,
    ),
]


def _assistant_with_tools(queries=(), commands=()):
    """One `ai` step handed these tools — the shape of `book_appointment` (whatsapp_inbox#197)."""
    tools = {}
    if queries:
        tools["queries"] = list(queries)
    if commands:
        tools["commands"] = list(commands)
    return {"steps": [{"id": "book", "kind": "ai", "prompt": "Book it.", "tools": tools}]}


def _finds_customer(query="customers.by_phone"):
    """The two deterministic lookups of the appointments recipe — `find_customer` and
    `resolve_customer` — reading the customer by the number she writes from."""
    return {
        "steps": [
            {"id": sid, "kind": "query", "query": query, "params": {"phone": "{{input.from}}"},
             "result": "first", "limit": 1}
            for sid in ("find_customer", "resolve_customer")
        ]
    }


# What `customers.by_phone` MENTIONED in the two releases around customers#81 (read off the real
# trees: `f6b0a35` = v2.3.46 and `120185f` = v2.3.47).
_BY_PHONE_2_3_46 = {"WITH", "wanted", "regexp_replace", "phone", "customers", "hub_id", "ltrim"}
_BY_PHONE_2_3_47 = _BY_PHONE_2_3_46 | {"hub_settings", "country_code", "calling_codes", "iso"}

HOME_COUNTRY_CASES = [
    (
        "the floor reads the business's country: a French number is not the local card",
        _finds_customer(),
        {"customers.by_phone": _BY_PHONE_2_3_47},
        0,
    ),
    (
        "🔴 whatsapp_inbox#202: the floor is a release whose `by_phone` lets ANY prefix through — "
        "`first` hands the French `33 600 111 222` the Spanish card `600 111 222`, and the "
        "appointment is booked on a stranger's record (one problem per step that reads it)",
        _finds_customer(),
        {"customers.by_phone": _BY_PHONE_2_3_46},
        2,
    ),
    (
        "🔴 only HALF the marker — a release that names `country_code` without the core's "
        "`hub_settings` did not learn the business's country from the one place that holds it",
        _finds_customer(),
        {"customers.by_phone": _BY_PHONE_2_3_46 | {"country_code"}},
        2,
    ),
    (
        "the floor could not be read — `main()` skipped it out loud; guessing here would invent "
        "a floor",
        _finds_customer(),
        {},
        0,
    ),
    (
        "the query does not exist at the floor at all — `floor_read_column_problems` already "
        "says so, once; saying it twice is noise",
        _finds_customer(),
        {"customers.by_phone": ABSENT_AT_FLOOR},
        0,
    ),
    (
        "a step reading ANOTHER customers query is not a number match and demands nothing here",
        _finds_customer(query="customers.get"),
        {"customers.get": {"id", "name"}},
        0,
    ),
]


UNFLOORED_READ_CASES = [
    (
        "every neighbour the recipe reads through a `query` step has its floor",
        _confirmation(),
        {"appointments": "1.1.77"},
        0,
    ),
    (
        "🔴 whatsapp_inbox#173: the neighbour's floor was deleted from `requires.json` — the hub "
        "offers the recipe to ANY copy of it, and the floor rules above read nothing to fail on",
        _confirmation(),
        {},
        1,
    ),
    (
        "a floor for some OTHER neighbour does not cover this one",
        _confirmation(),
        {"customers": "2.3.45"},
        1,
    ),
    (
        "🔴 whatsapp_inbox#197: the assistant is handed a neighbour's QUERY as a tool and that "
        "neighbour has no floor — the hub offers the recipe next to a copy without the read",
        _assistant_with_tools(queries=["services.services.list"]),
        {},
        1,
    ),
    (
        "🔴 whatsapp_inbox#197: the assistant is handed a neighbour's COMMAND as a tool and that "
        "neighbour has no floor",
        _assistant_with_tools(commands=["customers.create"]),
        {},
        1,
    ),
    (
        "every neighbour behind the assistant's tools has its floor; its own tools owe none",
        _assistant_with_tools(
            queries=["services.services.list", "whatsapp_inbox.conversations.last_offer"],
            commands=["customers.create", "whatsapp_inbox.conversations.remember_offer"],
        ),
        {"services": "1.1.7", "customers": "2.3.45"},
        0,
    ),
    (
        "one problem per unfloored neighbour, not one per tool it hands over",
        _assistant_with_tools(queries=["staff.members.list", "staff.schedules.list_for_member"]),
        {},
        1,
    ),
    (
        "🔴 a neighbour's `command` step with no floor is the same hole as a read",
        {"steps": [{"id": "book", "kind": "command", "command": "appointments.appointments.create"}]},
        {},
        1,
    ),
]


def self_check():
    """The mutants of the rules above, run every time, before any real document is opened."""
    problems = booking_tables_disagreement_problems()
    for rule in SELF_CHECKED_RULES:
        if rule not in DOCUMENT_RULES:
            problems.append(
                f"`{rule.__name__}` is proved here but is not in DOCUMENT_RULES: the ledger would "
                f"stop demanding that it ever met a real template, and its cases would keep passing"
            )
    for label, cdef, perms, expected in CLASSIFICATION_CASES:
        got = command_only_answers(cdef, perms)
        if got is not expected:
            problems.append(
                f"the battery's own classification is wrong — {label}: expected {expected}, "
                f"got {got}"
            )
    for label, name, doc, expected in UNATTENDED_CASES:
        got = unattended_problems(name, doc)
        if len(got) != expected:
            problems.append(
                f"the battery's own «unattended means unattended» rule is wrong — {label}: "
                f"expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, name, doc, expected in TAPPABLE_CASES:
        got = tappable_option_problems(name, doc)
        if len(got) != expected:
            problems.append(
                f"the battery's own «she taps it» rule is wrong — {label}: expected {expected} "
                f"problem(s), got {len(got)}: {got}"
            )
    for label, source, translation, same in SHAPE_CASES:
        got = structural_shape({"steps": [source]}) == structural_shape({"steps": [translation]})
        if got is not same:
            problems.append(
                f"the battery's own «a translation is words» rule is wrong — {label}: expected "
                f"{'the same' if same else 'a different'} automation, got the "
                f"{'same' if got else 'opposite'}"
            )
    for label, name, doc, expected in PARKING_CASES:
        got = parking_producer_problems(name, doc, _FIXTURE_COMMANDS, _FIXTURE_READS)
        if len(got) != expected:
            problems.append(
                f"the battery's own «the producer can finish» rule is wrong — {label}: expected "
                f"{expected} problem(s), got {len(got)}: {got}"
            )
    for label, name, doc, expected in ONLY_CUSTOMER_CASES:
        got = only_the_customer_problems(name, doc)
        if len(got) != expected:
            problems.append(
                f"the battery's own «a customer, and only now» rule is wrong — {label}: expected "
                f"{expected} problem(s), got {len(got)}: {got}"
            )
    for label, name, doc, expected in HOUR_CASES:
        got = hour_choice_problems(name, doc)
        if len(got) != expected:
            problems.append(
                f"the battery's own «the model never picks the hour» rule is wrong — {label}: "
                f"expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, name, doc, expected in BIRTH_STATUS_CASES:
        got = birth_status_problems(name, doc)
        if len(got) != expected:
            problems.append(
                f"the battery's own «tell her what really happened» rule is wrong — {label}: "
                f"expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, name, doc, floors, expected in BIRTH_READING_CASES:
        got = birth_status_reading_problems(name, doc, floors)
        if len(got) != expected:
            problems.append(
                f"the battery's own «read the switch as it comes back» rule is wrong — {label}: "
                f"expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, families, expected in LEDGER_CASES:
        got = unattended_ledger_problems("(self-check)", {}, families)
        if len(got) != expected:
            problems.append(
                f"the battery's own «the ledger and `flows/` agree» rule is wrong — {label}: "
                f"expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, booked, expected in RECIPE_CASES:
        got = shipped_recipe_problems("(self-check)", {}, booked)
        if len(got) != expected:
            problems.append(
                f"the battery's own «every wording has a recipe that ships» rule is wrong — "
                f"{label}: expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, name, doc, expected in TABLE_SCOPE_CASES:
        got = unowned_table_problems(name, doc)
        if len(got) != expected:
            problems.append(
                f"the battery's own «a booking that is not yours» rule is wrong — {label}: "
                f"expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, name, doc, expected in MOVE_CASES:
        got = moving_problems(name, doc)
        if len(got) != expected:
            problems.append(
                f"the battery's own «moving is one call, never two» rule is wrong — {label}: "
                f"expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, name, doc, pins, expected in PIN_CASES:
        got = unpinned_command_problems(name, doc, pins)
        if len(got) != expected:
            problems.append(
                f"the battery's own «the narrow value lives in the grant» rule is wrong — {label}: "
                f"expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, name, doc, pins, expected in QUERY_PIN_CASES:
        got = unpinned_query_problems(name, doc, pins)
        if len(got) != expected:
            problems.append(
                f"the battery's own «a diary is somebody's» rule is wrong — {label}: "
                f"expected {expected} problem(s), got {len(got)}: {got}"
            )
    # The sidecar READERS are anchored on a fixture, because a blind reader is invisible to the
    # tables above: `unpinned_query_problems` is silent when handed no pin at all (that red belongs
    # to `main()`, by design), so a `declared_query_pins` that stopped seeing `query` grants — a
    # one-word slip, measured in review — leaves every real document green while every case above
    # keeps passing, since those are handed their pins directly. The positive has to be seen by the
    # reader itself, in both shapes a sidecar may take, and its twin is held to the same standard.
    with tempfile.TemporaryDirectory() as tmp:
        grants = [
            {"kind": "command", "value": "x.write", "payload": {"channel": "customer"}},
            {"kind": "query", "value": "x.read", "payload": {"customer_id": "steps.r.id"}},
            {"kind": "query", "value": "x.wide"},
        ]
        for shape, body in (("an object with `grants`", {"grants": grants}), ("a bare list", grants)):
            path = pathlib.Path(tmp) / "fixture.grants.json"
            path.write_text(json.dumps(body))
            for reader, expected in (
                (declared_query_pins, {"x.read": {"customer_id": "steps.r.id"}, "x.wide": {}}),
                (declared_command_pins, {"x.write": {"channel": "customer"}}),
            ):
                got = reader(path)
                if got != expected:
                    problems.append(
                        f"the battery's own sidecar reader `{reader.__name__}` is blind on {shape}: "
                        f"expected {expected}, got {got} — a reader that misses a pin leaves the "
                        f"«the narrow value lives in the grant» rules silent on every real "
                        f"document, and nothing else here would notice"
                    )
    for label, name, doc, families, expected in TRIGGER_CASES:
        got = family_trigger_problems(name, doc, families)
        if len(got) != expected:
            problems.append(
                f"the battery's own «each family waits for what its row says» rule is wrong — "
                f"{label}: expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, name, doc, expected in CONFIRMATION_CASES:
        got = confirmation_notice_problems(name, doc)
        if len(got) != expected:
            problems.append(
                f"the battery's own «the salon confirms and she is told» rule is wrong — "
                f"{label}: expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, name, doc, families, expected in INSTRUCTION_CASES:
        got = missing_instruction_problems(name, doc, families)
        if len(got) != expected:
            problems.append(
                f"the battery's own «an instruction may not be lost in translation» rule is wrong "
                f"— {label}: expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, doc, expected in STEP_KEY_CASES:
        got = unknown_step_key_problems("(self-check)", doc)
        if len(got) != expected:
            problems.append(
                f"the battery's own «a key the kernel does not know» rule is wrong — {label}: "
                f"expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, name, doc, expected in OWN_CUSTOMER_CASES:
        got = own_customer_only_problems(name, doc)
        if len(got) != expected:
            problems.append(
                f"the battery's own «one customer, and only that one» rule is wrong — {label}: "
                f"expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, doc, expected in SILENCE_CASES:
        got = silence_problems("(self-check)", doc)
        if len(got) != expected:
            problems.append(
                f"the battery's own «say something back» rule is wrong — {label}: expected "
                f"{expected} problem(s), got {len(got)}: {got}"
            )
    for label, doc, expected in REFUSAL_CASES:
        got = mute_refusal_problems("(self-check)", doc)
        if len(got) != expected:
            problems.append(
                f"the battery's own «a «no» reaches the customer too» rule is wrong — {label}: "
                f"expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, doc, expected in ENDING_CASES:
        got = unanswered_ending_problems("(self-check)", doc)
        if len(got) != expected:
            problems.append(
                f"the battery's own «nobody decided, or the write broke» rule is wrong — {label}: "
                f"expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, doc, expected in ASSISTANT_FAILURE_CASES:
        got = assistant_failure_problems("(self-check)", doc)
        if len(got) != expected:
            problems.append(
                f"the battery's own «the assistant failed, tell her anyway» rule is wrong — "
                f"{label}: expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, doc, expected in ASSISTANT_SILENCE_CASES:
        got = assistant_silence_problems("(self-check)", doc)
        if len(got) != expected:
            problems.append(
                f"the battery's own «the assistant said nothing, tell her anyway» rule is wrong — "
                f"{label}: expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, doc, expected in TOOL_CASES:
        got = undeclared_tool_problems("(self-check)", doc, _KNOWN_OPS)
        if len(got) != expected:
            problems.append(
                f"the battery's own «the prompt only orders what it was handed» rule is wrong — "
                f"{label}: expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, doc, expected in ORDER_CASES:
        got = unordered_tool_problems("(self-check)", doc)
        if len(got) != expected:
            problems.append(
                f"the battery's own «every tool handed over is ordered» rule is wrong — {label}: "
                f"expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, doc, expected in BUDGET_CASES:
        got = budget_problems("(self-check)", doc)
        if len(got) != expected:
            problems.append(
                f"the battery's own `max_iters` rule is wrong — {label}: expected {expected} "
                f"problem(s), got {len(got)}: {got}"
            )
    for label, doc, expected in ENUM_CASES:
        got = enum_value_problems("(self-check)", doc, _FIXTURE_ENUMS)
        if len(got) != expected:
            problems.append(
                f"the battery's own «the value ordered is one the schema accepts» rule is wrong — "
                f"{label}: expected {expected} problem(s), got {len(got)}: {got}"
            )
    problems += _enum_reading_problems()
    for label, doc, expected in IDENTITY_CASES:
        got = identified_cancellation_problems("(self-check)", doc)
        if len(got) != expected:
            problems.append(
                f"the battery's own «the customer channel says who is asking» rule is wrong — "
                f"{label}: expected {expected} problem(s), got {len(got)}: {got}"
            )
    problems += _identity_reading_problems()
    for label, doc, floor_props, expected in FLOOR_CASES:
        got = floor_field_problems("(self-check)", doc, floor_props)
        if len(got) != expected:
            problems.append(
                f"the battery's own «the floor already takes what we send» rule is wrong — "
                f"{label}: expected {expected} problem(s), got {len(got)}: {got}"
            )
    problems += _floor_reading_problems()
    for label, doc, floor_emits, expected in FLOOR_TRIGGER_CASES:
        got = floor_trigger_problems("(self-check)", doc, floor_emits)
        if len(got) != expected:
            problems.append(
                f"the battery's own «the floor already declares the event» rule is wrong — "
                f"{label}: expected {expected} problem(s), got {len(got)}: {got}"
            )

    problems += _floor_read_reading_problems()
    for label, doc, floor_columns, expected in FLOOR_READ_CASES:
        got = floor_read_column_problems("(self-check)", doc, floor_columns)
        if len(got) != expected:
            problems.append(
                f"the battery's own «the floor already answers the columns we read» rule is "
                f"wrong — {label}: expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, doc, floor_columns, expected in HOME_COUNTRY_CASES:
        got = home_country_match_problems("(self-check)", doc, floor_columns)
        if len(got) != expected:
            problems.append(
                f"the battery's own «the floor reads the business's country» rule is wrong — "
                f"{label}: expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, doc, floors, expected in UNFLOORED_READ_CASES:
        got = unfloored_read_problems("(self-check)", doc, floors)
        if len(got) != expected:
            problems.append(
                f"the battery's own «every neighbour we read has a floor» rule is wrong — "
                f"{label}: expected {expected} problem(s), got {len(got)}: {got}"
            )

    for label, name, doc, expected in POLICY_CASES:
        got = policy_problems(name, doc, _FIXTURE_COMMANDS, _FIXTURE_READS)
        if len(got) != expected:
            problems.append(
                f"the battery's own `policy` rule is wrong — {label}: expected {expected} "
                f"problem(s), got {len(got)}: {got}"
            )
    return problems


def main():
    problems, skipped = self_check(), []
    ledger, inspected = set(), []

    docs = flow_documents()
    if not docs:
        print(
            "FAIL  flows/ carries no *.flow.json — there is no template to distribute"
        )
        return 1

    # 1) The contract the hub itself serves.
    #
    # Two ways this layer can be unavailable, and BOTH have to skip loudly rather than take the
    # battery down with them: on a CI runner the hub checkout is simply not there, and outside a
    # virtualenv `jsonschema` is not importable (PEP 668 refuses to install it system-wide). It
    # used to raise `ModuleNotFoundError` in the second case, which aborted the run before layers
    # 2-6 — the ones that need no dependency at all — had said anything.
    #
    # Both stop being skips where a hub is PROMISED (`ERPLORA_HUB_DIR` declared, or a CI run): there
    # the skip is exactly the silence whatsapp_inbox#214 removed, so it is a FAIL with its code.
    validator = None
    unavailable = None
    if not HUB_SCHEMA.is_file():
        unavailable = (
            "hub_schema_missing",
            f"flow.schema.json not found at {HUB_SCHEMA} — the documents were NOT validated",
        )
    else:
        try:
            import jsonschema

            validator = jsonschema
        except ImportError:
            unavailable = (
                "jsonschema_missing",
                f"`jsonschema` is not installed — the documents were NOT validated against "
                f"{HUB_SCHEMA}; every other layer below still ran",
            )
    if unavailable is not None:
        code, why = unavailable
        if SCHEMA_REQUIRED:
            problems.append(
                f"[{code}] {why}; a hub was promised here "
                f"(ERPLORA_HUB_DIR={HUB_DECLARED or 'unset'}, CI={os.environ.get('CI', 'unset')})"
            )
        else:
            skipped.append(why)

    if validator is not None:
        print(f"SCHEMA  {HUB_SCHEMA}")
        schema = json.loads(HUB_SCHEMA.read_text())
        for path in docs:
            try:
                validator.validate(json.loads(path.read_text()), schema)
            except validator.ValidationError as e:
                where = "/".join(str(p) for p in e.absolute_path) or "(root)"
                problems.append(
                    f"{path.name} is not a valid flow document at `{where}`: {e.message}"
                )

    manifests = workspace_manifests()
    if manifests is None:
        contracts, definitions, commands_def, resolved = None, None, None, None
        read_perms = {}
        skipped.append(
            "the module workspace is not next to this repo — query/command names and the "
            "parameter vocabularies were NOT verified"
        )
    else:
        resolved = resolved_modules(manifests)

    # 1b) WHICH copy answered, and was it recent enough.
    #
    # Layer 3 below is only worth what the manifests it reads are worth, and a workspace is a pile
    # of checkouts at whatever commit somebody left them on. This is the half that was missing when
    # whatsapp_inbox#52 shipped: the canonical `appointments/` checkout sat 13 releases behind, so
    # the battery resolved `appointments.availability.slots` against a manifest where it was still
    # a `query` and said OK. A green that depends on how stale the machine is, is not a green — so
    # the versions it resolved against are PRINTED, and a copy below the floor this repo declares
    # is a FAIL, not a footnote.
    if resolved is not None:
        for path in sorted({floors_of(d) for d in docs}):
            if not path.is_file():
                problems.append(
                    f"flows/ has no `{path.name}`: without a declared floor these templates are "
                    f"checked against whatever version of its neighbours this machine happens to "
                    f"hold, and a stale checkout turns a red into a green"
                )
                continue
            floors = (json.loads(path.read_text()) or {}).get("modules") or {}
            for module_id in sorted(floors):
                want = version_tuple(floors[module_id])
                if want is None:
                    problems.append(
                        f"{path.name}: `{module_id}` floor {floors[module_id]!r} is not a version"
                    )
                    continue
                target = resolved.get(module_id)
                if target is None:
                    skipped.append(
                        f"{path.name} requires `{module_id}` >= {floors[module_id]}, and no such "
                        f"module is in the workspace — its operations were NOT verified"
                    )
                    continue
                module_dir, manifest = target
                have = version_tuple(manifest.get("version"))
                if have is not None and have >= want:
                    print(
                        f"RESOLVED  {module_id}@{manifest.get('version')} "
                        f"(needs >= {floors[module_id]}) from {module_dir.name}/"
                    )
                    continue

                # The checkout that owns the name is too old to answer. Rather than trust it, look
                # for a copy in the workspace that DOES meet the floor and say out loud that a
                # fallback answered — the fleet keeps worktrees of its modules next door, and one of
                # them being current is the ordinary case on a machine mid-batch.
                better = next(
                    (
                        (d, m)
                        for d, m in copies_of(manifests, module_id)
                        if (version_tuple(m.get("version")) or ()) >= want
                    ),
                    None,
                )
                if better is None:
                    problems.append(
                        f"no copy of `{module_id}` in this workspace reaches {floors[module_id]} "
                        f"(the newest is {manifest.get('version')} in {module_dir}). Every name "
                        f"below would be resolved against a manifest that no longer describes what "
                        f"the hub runs, which is how a red becomes a green — refresh it with "
                        f"`git -C {module_dir} pull --ff-only` before believing this battery"
                    )
                    continue
                resolved[module_id] = better
                print(
                    f"RESOLVED  {module_id}@{better[1].get('version')} "
                    f"(needs >= {floors[module_id]}) from {better[0].name}/ — the checkout that "
                    f"owns the name, {module_dir.name}/, is {manifest.get('version')} and too old "
                    f"to answer"
                )

    if resolved is not None:
        contracts = workspace_contracts(resolved)
        definitions = query_definitions(resolved)
        commands_def = command_definitions(resolved)
        read_perms = module_read_permissions(resolved)
        enums = payload_enums(commands_def)
        identity_props = payload_properties(commands_def)
        # The release `BIRTH_STATUS_BOOLEAN_SINCE` pins is the one that really made the switch
        # a boolean, read out of the neighbour's history (whatsapp_inbox#152).
        since_problems, since_skips = boolean_since_problems(definitions)
        problems += since_problems
        skipped += since_skips

    # Which family books what, read once: `shipped_recipe_problems` judges the SET of
    # documents, and the set is not visible from any one of them.
    booked = booked_families((path, json.loads(path.read_text())) for path in docs)

    # …and which families ship AT ALL, for the same reason: `PINNED_INSTRUCTIONS` names families,
    # and a row pointing at a name nothing carries is a guard over nothing.
    shipped_families = {path.name.split(".")[0] for path in docs}

    # …and what each family's declared FLOOR really takes, read once per `requires.json` because it
    # walks the neighbour's git history and both languages of a family share the same floor.
    floor_props_by_family = {}
    floor_emits_by_family = {}
    floor_reads_by_family = {}

    for path in docs:
        doc = json.loads(path.read_text())

        # 2) The grants, both ways.
        gpath = grants_of(path)
        if not gpath.is_file():
            problems.append(
                f"{path.name} has no `{gpath.name}`: a document without its grants is a flow that saves and then dies with `flow.grant_denied`"
            )
            continue
        inspected.append(path.name)
        needed, declared = needed_grants(doc), declared_grants(gpath)
        for kind, value in sorted(needed - declared):
            problems.append(
                f"{path.name} needs the grant `{kind}` → `{value}` and {gpath.name} does not declare it"
            )
        for kind, value in sorted(declared - needed):
            problems.append(
                f"{gpath.name} declares the grant `{kind}` → `{value}` that no step of {path.name} uses: an authorisation nobody spends is one the owner was asked for and cannot audit"
            )

        # 3) Names that exist.
        if contracts is not None:
            queries, commands = contracts
            for kind, value in sorted(needed):
                if kind == "query" and value not in queries:
                    problems.append(
                        f"{path.name} offers the query `{value}`, which no installed module declares"
                    )
                if kind == "command" and value not in commands:
                    problems.append(
                        f"{path.name} proposes the command `{value}`, which no installed module declares"
                    )
                if kind == "recipient_query":
                    q = value.split("#", 1)[0]
                    if q not in queries:
                        problems.append(
                            f"{path.name} addresses its message through `{q}`, which no installed module declares"
                        )

        # 3a) `policy` against what each declared command actually does — see `policy_problems`.
        if commands_def is not None:
            problems += applied(ledger, policy_problems, path.name, doc, commands_def, read_perms)

        # 3a-bis) …and it SAYS so afterwards (whatsapp_inbox#58). Needs no manifest: it is about the
        # shape of the document, so it runs on a bare checkout too.
        problems += applied(ledger, silence_problems, path.name, doc)

        # 3a-bis-i) …and it says something back when the answer is «no» too (whatsapp_inbox#67).
        # The ending `silence_problems` cannot see: the run used to die AT the rejection.
        problems += applied(ledger, mute_refusal_problems, path.name, doc)
        # …and the two nobody could write until hub#1634/hub#1635: the silence and the breakage.
        problems += applied(ledger, unanswered_ending_problems, path.name, doc)
        # …and the ending nobody writes down: the ASSISTANT itself fails (whatsapp_inbox#122).
        problems += applied(ledger, assistant_failure_problems, path.name, doc)
        problems += applied(ledger, assistant_silence_problems, path.name, doc)

        # 3a-bis-ii) …and a family that CALLS itself unattended really is (whatsapp_inbox#58): the
        # other half of the exception `policy_problems` grants it. Needs no manifest either.
        problems += applied(ledger, unattended_problems, path.name, doc)

        # 3a-bis-iii) …and, in that family, the step that can book still says in so many words that
        # it never picks the hour (whatsapp_inbox#58, reviewer mutant N2). Prose, pinned on purpose.
        problems += applied(ledger, hour_choice_problems, path.name, doc)

        # 3a-bis-iii-bis) …and every booking that wording exists for is one this module really
        # SHIPS, in both families (whatsapp_inbox#60). Needs no manifest: it reads `flows/`.
        problems += applied(ledger, birth_status_problems, path.name, doc)

        # …and the sentence that picks between those endings describes the switch in the shape
        # its read really answers, over a floor where it answers it (whatsapp_inbox#152).
        fpath = floors_of(path)
        family_floors = (
            (json.loads(fpath.read_text()) or {}).get("modules") or {} if fpath.is_file() else {}
        )
        problems += applied(
            ledger, birth_status_reading_problems, path.name, doc, family_floors
        )

        problems += applied(ledger, shipped_recipe_problems, path.name, doc, booked)

        problems += applied(
            ledger, unattended_ledger_problems, path.name, doc, set(booked)
        )

        # 3a-bis-iii-ter) …and no step that writes with NOBODY watching is handed an operation on a
        # booking that already exists, because `reservations` cannot tell whose it is
        # (whatsapp_inbox#60, reviewer mutant MX-b; reopens with ERPlora/reservations#50).
        problems += applied(ledger, unowned_table_problems, path.name, doc)

        # 3a-bis-iv) …and the appointment writer of BOTH families can move an appointment, looks
        # up whose it is before it does, and says that moving never becomes cancel-plus-book
        # (whatsapp_inbox#74).
        problems += applied(ledger, moving_problems, path.name, doc)

        # 3a-bis-v) …and no step of either family holds the address book, so the customer this
        # run is about is the one the PHONE picked out and never the one the message named
        # (whatsapp_inbox#103). Needs no manifest: it is the document's own shape.
        problems += applied(ledger, own_customer_only_problems, path.name, doc)
        problems += applied(ledger, unknown_step_key_problems, path.name, doc)

        # 3a-bis-vi) …and the narrow value the salon's own cancellation rules hang on travels in
        # the GRANT and not in the prompt, wherever nobody is watching (whatsapp_inbox#100).
        # Reads the sidecar, never a manifest: a bare checkout judges it too.
        problems += applied(
            ledger, unpinned_command_problems, path.name, doc, declared_command_pins(gpath)
        )
        problems += applied(
            ledger, unpinned_query_problems, path.name, doc, declared_query_pins(gpath)
        )

        # 3a-bis-vii) …and the instructions that may not be lost are in the document, IN ITS OWN
        # LANGUAGE (whatsapp_inbox#112). Reads nothing but the prompts and the names in `flows/`.
        problems += applied(
            ledger, missing_instruction_problems, path.name, doc, shipped_families
        )

        # 3a-ter) …and every tool its prompts ORDER was actually handed over (whatsapp_inbox#61).
        # Needs the manifests: «is this a tool name or is it prose» is a question only they answer.
        if contracts is not None:
            problems += applied(
                ledger, undeclared_tool_problems, path.name, doc, contracts[0] | contracts[1]
            )

        # 3a-iv) …and the reverse: every tool handed over is one the prompt ORDERS
        # (whatsapp_inbox#61). Needs nothing: a bare checkout judges it too.
        problems += applied(ledger, unordered_tool_problems, path.name, doc)

        # 3a-v) `max_iters` within the hub's cap, hub checkout or not.
        problems += applied(ledger, budget_problems, path.name, doc)

        # 3a-vi) …and every value the prompt orders for an enum field is one the command's own
        # schema accepts (whatsapp_inbox#61). Needs the manifests: the schema lives next to them.
        if commands_def is not None:
            problems += applied(ledger, enum_value_problems, path.name, doc, enums)

        # 3a-vi-bis) …and when it orders `channel` = `customer` it also says WHO is asking
        # (whatsapp_inbox#82). Needs no manifest: the pair is named in `IDENTITY_BOUND_PAYLOAD`,
        # and `identity_field_problems` below is what keeps that table honest.
        problems += applied(ledger, identified_cancellation_problems, path.name, doc)

        # 3a-vi-ter) …and the table that rule reads still describes the command's REAL schema
        # (whatsapp_inbox#82). Needs the manifests: the schema lives next to them.
        if commands_def is not None:
            problems += applied(
                ledger, identity_field_problems, path.name, doc, identity_props, enums
            )

        # 3a-vi-quater) …and the command TOOK those fields already at the floor this family
        # declares, not just in the checkout this machine happens to hold (whatsapp_inbox#105).
        # The floor travels to the hub since hub#1611 and decides whether the recipe is OFFERED,
        # so a floor one release too low hands the recipe to a hub that refuses every call.
        if commands_def is not None:
            fpath = floors_of(path)
            if fpath not in floor_props_by_family:
                declared = (json.loads(fpath.read_text()) or {}).get("modules") or {} if fpath.is_file() else {}
                floor_props_by_family[fpath], floor_skips = floor_payload_properties(
                    declared, commands_def, resolved
                )
                skipped += [f"{fpath.name}: {why}" for why in floor_skips]
            problems += applied(
                ledger, floor_field_problems, path.name, doc, floor_props_by_family[fpath]
            )

        # 3a-vi-quinquies) …and the neighbour ALREADY DECLARED the event this family waits on at
        # that same floor (whatsapp_inbox#125). The twin above holds the floor to what the
        # templates SEND; this one to what wakes them up, which is the half that decides whether
        # the automation ever runs at all.
        if resolved is not None:
            fpath = floors_of(path)
            if fpath not in floor_emits_by_family:
                declared = (json.loads(fpath.read_text()) or {}).get("modules") or {} if fpath.is_file() else {}
                floor_emits_by_family[fpath], emit_skips = floor_emitted_events(declared, resolved)
                skipped += [f"{fpath.name}: {why}" for why in emit_skips]
            problems += applied(
                ledger, floor_trigger_problems, path.name, doc, floor_emits_by_family[fpath]
            )

        # 3a-vi-septies) …and every neighbour this family reads HAS a floor to hold it to
        # (whatsapp_inbox#173). Pure — it reads the document and its `requires.json`, never a
        # neighbour — so it runs with or without the workspace next door.
        fpath = floors_of(path)
        declared = (json.loads(fpath.read_text()) or {}).get("modules") or {} if fpath.is_file() else {}
        problems += applied(ledger, unfloored_read_problems, path.name, doc, declared)

        # 3a-vi-sexies) …and the neighbour already ANSWERED the columns this family reads back at
        # that same floor (whatsapp_inbox#146): a column the floor lacks resolves to nothing, and
        # the customer receives the placeholder.
        if definitions is not None:
            fpath = floors_of(path)
            declared = (json.loads(fpath.read_text()) or {}).get("modules") or {} if fpath.is_file() else {}
            cached = floor_reads_by_family.setdefault(fpath, {})
            wanted = {
                s.get("query")
                for s in doc.get("steps") or []
                if s.get("kind") == "query" and isinstance(s.get("query"), str)
            } - set(cached)
            if wanted:
                got, read_skips = floor_read_columns(declared, definitions, resolved, wanted)
                cached.update(got)
                cached.update({q: None for q in wanted - set(got)})
                skipped += [f"{fpath.name}: {why}" for why in read_skips]
            problems += applied(
                ledger,
                floor_read_column_problems,
                path.name,
                doc,
                {q: c for q, c in cached.items() if c is not None},
            )
            # …and the customer it finds by her number is one of the BUSINESS's country at that
            # floor (whatsapp_inbox#202): same reading, so it rides the same cache.
            problems += applied(
                ledger,
                home_country_match_problems,
                path.name,
                doc,
                {q: c for q, c in cached.items() if c is not None},
            )

        # 3b) Every parameter is a word the query it addresses actually knows.
        #
        # A name that exists is not a name that filters. `whatsapp_inbox.conversations.list`
        # declares `wa_contact_id` as a filter, so the form ON THE WIRE is `f_wa_contact_id`; the
        # bare column name is nobody's parameter. This is the layer that reads the manifest of the
        # module being addressed and says so.
        if definitions is not None:
            for step_id, qid, names, where in addressed_queries(doc):
                target = definitions.get(qid)
                if target is None:
                    continue  # already reported above as a name no module declares
                accepted = query_vocabulary(*target)
                if accepted is None:
                    skipped.append(
                        f"{path.name}: the vocabulary of `{qid}` could not be read (its SQL or "
                        f"`schema` file is missing) — step `{step_id}` was NOT verified"
                    )
                    continue
                for name in names:
                    if name in accepted:
                        continue
                    hint = ""
                    if f"f_{name}" in accepted:
                        hint = f" — it is a declared filter, so on the wire it is `f_{name}`"
                    elif f"f_{name}_from" in accepted:
                        hint = (
                            f" — it is a `range` filter, so on the wire it is "
                            f"`f_{name}_from` / `f_{name}_to`"
                        )
                    problems.append(
                        f"{path.name} step `{step_id}` passes `{name}` in `{where}` to `{qid}`, "
                        f"which does not accept it{hint}. Accepted: "
                        f"{', '.join(sorted(accepted))}"
                    )

        # 3a-vii) …and the trigger only wakes up for a customer writing NOW, on every core this
        # module claims to run on (whatsapp_inbox#90). Needs no manifest: filter and input map are
        # the document's own shape.
        problems += applied(ledger, only_the_customer_problems, path.name, doc)
        problems += applied(ledger, tappable_option_problems, path.name, doc)

        # 3a-viii) …and every step that owes DATA can FINISH: one that may propose a WRITE never
        # reaches `flow_answer`, so its write neither parks nor runs — and, when a list sends its
        # rows, they leave for Meta as `null` (hub#1639).
        # Manifest-aware — telling a read from a write needs the module that declares it.
        if commands_def is not None:
            problems += applied(
                ledger, parking_producer_problems, path.name, doc, commands_def, read_perms
            )

        # The trigger this whole issue is about: a template that listens to something else is a
        # different product wearing the same file name. Per FAMILY since whatsapp_inbox#125 —
        # this module now ships one recipe that legitimately waits on the diary instead of on an
        # incoming message, and a blanket demand could only fail it or be deleted.
        problems += applied(
            ledger, family_trigger_problems, path.name, doc, shipped_families
        )

        # …and that recipe really closes the loop it was written for: the salon confirms and the
        # customer is told, on the number the DIARY holds for her (whatsapp_inbox#125).
        problems += applied(ledger, confirmation_notice_problems, path.name, doc)

    # 3c) …and every rule above actually MET every document that reached this far. Waived only for
    # the layer that was skipped out loud (no manifests next door → no `policy_problems`).
    waived = (
        {
            policy_problems.__name__,
            undeclared_tool_problems.__name__,
            enum_value_problems.__name__,
            identity_field_problems.__name__,
            floor_field_problems.__name__,
            floor_trigger_problems.__name__,
            floor_read_column_problems.__name__,
            home_country_match_problems.__name__,
            parking_producer_problems.__name__,
        }
        if commands_def is None
        else set()
    )
    for name in inspected:
        for rule in DOCUMENT_RULES:
            if rule.__name__ in waived or (rule.__name__, name) in ledger:
                continue
            problems.append(
                f"{name} never went through `{rule.__name__}`: self_check() only proves that rule "
                f"on synthetic documents, so a template it never met is green for no reason — "
                f"apply it in main() through `applied()`"
            )

    # 4) The translations are the same automation.
    families = {}
    for path in docs:
        family, locale = path.name.split(".")[0], path.name.split(".")[1]
        families.setdefault(family, {})[locale] = json.loads(path.read_text())
    for family, byloc in families.items():
        if "en" not in byloc:
            problems.append(
                f"{family}: there is no `.en.flow.json` — English is the source (ADR-0055/0199)"
            )
            continue
        source = structural_shape(byloc["en"])
        for locale, doc in byloc.items():
            if locale == "en":
                continue
            if structural_shape(doc) != source:
                problems.append(
                    f"{family}.{locale}.flow.json is no longer the same automation as the English source: only the human text may differ"
                )

    for s in skipped:
        print(f"SKIPPED  {s}")
    for p in problems:
        print(f"FAIL  {p}")
    if problems:
        return 1
    print(
        f"OK: {len(docs)} flow template(s) parse, and their grants cover exactly what their steps do"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

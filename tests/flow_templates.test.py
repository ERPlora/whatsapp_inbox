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
import pathlib
import re
import sys
import tempfile

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
FLOWS_DIR = MODULE_DIR / "flows"
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())

# The hub checkout, when this runs from the monorepo. Absent on a CI runner that only clones this
# repo — the schema check then SKIPS loudly instead of passing quietly.
HUB_SCHEMA = MODULE_DIR.parents[2] / "hub" / "schemas" / "flow.schema.json"
WORKSPACE_MODULES = MODULE_DIR.parent


def flow_documents():
    return sorted(FLOWS_DIR.glob("*.flow.json"))


def grants_of(doc_path):
    """The `.grants.json` that travels with a document (one per template family)."""
    family = doc_path.name.split(".")[0]
    return FLOWS_DIR / f"{family}.grants.json"


# How a template DECLARES that it runs with nobody watching (whatsapp_inbox#58). It is the file
# name and not a key inside the document because the document has nowhere to put it: the hub's
# `flow.schema.json` is `additionalProperties: false` at the root, so an invented `"unattended":
# true` would be REFUSED by `PUT /api/hub/flows` — the declaration has to live where the kernel
# does not read. The family name also survives translation, which the flow's `name` does not.
UNATTENDED_SUFFIX = "-unattended"


def is_unattended(name):
    """Does this document belong to the family that books with nobody watching?"""
    return name.split(".")[0].endswith(UNATTENDED_SUFFIX)


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


def quoted_steps(doc):
    """Step ids that some OTHER step interpolates (`{{steps.<id>.…}}`) — who feeds whom.

    Read the way the hub reads it (`flows::def::render_template`): every `{{ … }}` pair, the path
    TRIMMED before it is resolved. So `{{ steps.look.text }}` names `look` exactly as
    `{{steps.look.text}}` does — a guard that only knew the unspaced spelling let the two-step
    workaround back in with one space.
    """
    out = set()
    for step in doc.get("steps", []):
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
    quoted = quoted_steps(doc)
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
    """Indexes of the `ai` steps that can PROPOSE a write — the ones a customer waits on."""
    out = []
    for i, step in enumerate(doc.get("steps", [])):
        if step.get("kind") != "ai":
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
# layer only runs with the hub checkout next door (a CI runner has none): this one needs nothing, so
# the cap holds on a bare checkout too.
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


def identity_field_problems(name, doc, props):
    """Every field `IDENTITY_BOUND_PAYLOAD` names is one the command's own schema really declares.

    A document rule that never reads the document, and on purpose: what it needs is the ledger. As
    a one-off call in `main()` it was the only check here that nothing required — deleting its
    single line let `appointments` rename or drop `customer_id` with this battery green over
    templates that would then fail on every cancellation (measured: the mutant survived). Registered
    like every other rule, that deletion is refused by name.
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


# ── «a rule with no recipe is a promise nothing keeps» ────────────────────────────────────────
#
# whatsapp_inbox#60. `BOOKING_RULES` is the table of everything this channel knows how to book
# unattended, and until this rule existed a row could sit in it with no document spending it: the
# wording pinned, `hour_choice_problems` green — silently, because that rule only judges documents
# that HAND the command — and the restaurant that connected its WhatsApp offered the two recipes of
# a hairdresser and nothing it could use. That is the issue exactly: not a broken template, a
# missing one, and every rule here was green over it.
#
# BOTH families or neither, because `flows/README.md` sells the choice and the business makes it at
# install: only the attended one leaves the restaurant that runs its WhatsApp alone waiting for an
# approval nobody will give at 3 AM; only the unattended one leaves the one that wants to read its
# bookings first with nothing to install.
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
        shipped = {f for f, commands in booked.items() if booking in commands}
        for unattended, label in ((True, "unattended"), (False, "attended")):
            if any(is_unattended(f) is unattended for f in shipped):
                continue
            problems.append(
                f"{name}: `{booking}` has its wording pinned in BOOKING_RULES and no {label} "
                f"family in `flows/` hands it, so the business that books with it has no recipe to "
                f"install and every other rule here stays green — they only judge the documents "
                f"that exist. Ship the pair, or take the row out of the table"
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
# What the trigger carries and no model can touch: the phone the message came FROM. It is mapped
# in `triggers[].input`, so it reaches a step as `{{input.from}}` — the one identity in this run
# that WhatsApp itself vouched for.
TRUSTED_PHONE = "input.from"
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


def moving_problems(name, doc):
    """Who may MOVE an appointment depends on who approves the write — whatsapp_inbox#74, #103.

    Judged on the step that hands `BOOKING_COMMAND`, which is the appointment writer of both
    families: what a customer can ask this channel for is decided there, in one place. Silent on
    every other step and on any future template that does not book appointments at all (table
    reservations, whatsapp_inbox#60): they owe nothing here.

    🔴 **And the answer is not the same for the two families, because the binding moving now has
    is one the MODEL can decline.** `appointments.appointments.cancel` binds its customer channel
    — handed `channel: "customer"`, the handler refuses an appointment whose `customer_id` is not
    the one asking. Since appointments#144 (v1.1.73) `reschedule` has the same two fields and the
    guard is EXTRACTED — `customer_identity_refusal(channel, payload, row)`, called by both doors
    — so the sentence this docstring used to carry, «it has no such field to bind», is no longer
    true and the reason for the split moved rather than disappeared.

    Where it moved: `channel` is an enum `staff|customer` whose **default is `staff`**, and the
    guard opens with `if channel != Customer { return Ok(None) }`. A model that simply omits the
    field is a receptionist as far as `appointments` is concerned, and the whole chain
    `customers.list` (searchable by name) → `list_for_customer` (takes any `customer_id`) →
    `reschedule` is back, inside the grants this template already asks for. What makes the field
    honest is the grant PINNING it (`payload` on a `command` grant, hub#1623) so the value is not
    the model's to choose — which is whatsapp_inbox#100, still open and waiting on hub#1623 being
    DEPLOYED rather than merged. Until then the unattended family keeps the verdict below for a
    new reason: not «there is nothing to pin», but «nothing pins it yet».

    Hence the split:

    * where a PERSON approves the write (`policy: "manual"` → `_flow_approvals`, and at the yes it
      runs exactly as proposed) the channel moves appointments, with the four marks below;
    * where NOBODY is watching (`policy: "auto"`, the family whatsapp_inbox#58 ships for the
      one-chair salon) the channel must NOT be able to move at all, and must say so in its prompt
      so the customer is told a person will answer instead of being ignored. The first half of
      reopening it is DONE — appointments#142 shipped as appointments#144 — and what is left is
      pinning the channel from this side (whatsapp_inbox#100), never the other way round.

    A missing `policy` counts as «nobody is watching»: this fails CLOSED, because the family that
    gets the write wrong is the one where nothing downstream notices.

    Four marks for the attended family, and each of them is one edit away from being lost:

    * **it can move** — `MOVE_COMMAND` in `tools.commands`. This is the red the issue itself is;
    * **it can look up WHAT it is moving** — `OWNED_APPOINTMENTS_QUERY` in `tools.queries`. This
      one is not a nicety and it is not symmetry with cancelling: the `channel` that would let
      `appointments` refuse somebody else's appointment defaults to `staff`, and nothing in this
      template pins it to `customer` yet (whatsapp_inbox#100), so the handler is not being asked
      to check whose appointment it is. The only thing standing between a customer and another
      person's hour is that the id came out of that query, for the customer resolved from her own
      phone number;
    * **the prompt says moving never becomes cancel-plus-book**, in the language it is written in,
      the same way and for the same reason `hour_choice_problems` pins its sentence: a model reads
      the prompt it was given, so a Spanish document carrying only the English sentence has the
      rule for nobody who reads it. A language this battery has no wording for is a document it
      cannot vouch for — the translation is added to `MOVE_RULE` in the same commit, or it does
      not ship;
    * **and the old «it cannot» order is gone** — `CANNOT_MOVE`. Adding the tool and leaving the
      sentence is the half-fix that passes everything else here.
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
        can_move = MOVE_COMMAND in (tools.get("commands") or [])
        # `manual` is the ONLY policy with a person in front of the write: it parks the proposal in
        # `_flow_approvals` and ends the turn. Anything else — `auto`, or a step that forgot to say
        # — writes inside the turn with nobody reading.
        if step.get("policy") != "manual":
            if can_move:
                problems.append(
                    f"{name} step `{sid}` runs with nobody watching "
                    f"(`policy: {step.get('policy')!r}`) and was handed `{MOVE_COMMAND}`: that "
                    f"command takes no `channel` and no `customer_id`, and its handler never "
                    f"checks whose appointment it is, so `customers.list` → "
                    f"`{OWNED_APPOINTMENTS_QUERY}` → move is a stranger's hour changed with no "
                    f"person in the loop and nothing downstream to refuse it. Pinning the payload "
                    f"in the grant (hub#1632) cannot help: there is no field to pin. It reopens "
                    f"with appointments#142 first, then whatsapp_inbox#103"
                )
                continue
            stale = CANNOT_MOVE.get(lang)
            if stale is None:
                problems.append(
                    f"{name} step `{sid}` cannot move an appointment and this battery has no "
                    f"wording of the «not yet» sentence for language `{lang}`: add the "
                    f"translation to CANNOT_MOVE in the same commit, or the customer who asks to "
                    f"change her hour is answered by whatever the model improvises"
                )
            elif stale not in prompt:
                problems.append(
                    f"{name} step `{sid}` cannot move an appointment and its prompt no longer "
                    f"says so («{stale}»): «can you change it to Thursday?» then falls to "
                    f"whatever the model decides — silence, or a SECOND appointment booked on top "
                    f"of the one she was trying to keep. Until appointments#142 lands, that "
                    f"sentence is what this family answers with"
                )
            continue
        if not can_move:
            problems.append(
                f"{name} step `{sid}` can book and cancel an appointment and cannot MOVE one "
                f"(`{MOVE_COMMAND}` is not in its `tools.commands`): «can you change it to "
                f"Thursday?» is the most common thing a customer writes and the only one this "
                f"channel answers with «somebody will get back to you», which is the wait the "
                f"automation exists to remove"
            )
            continue
        if OWNED_APPOINTMENTS_QUERY not in (tools.get("queries") or []):
            problems.append(
                f"{name} step `{sid}` can move an appointment and was never handed "
                f"`{OWNED_APPOINTMENTS_QUERY}`: since appointments#144 `{MOVE_COMMAND}` does take "
                f"`channel` + `customer_id`, but `channel` DEFAULTS to `staff` and nothing here "
                f"pins it to `customer` yet (whatsapp_inbox#100), so `appointments` is never "
                f"asked to refuse a move of somebody else's appointment — that query, filtered by "
                f"the customer resolved from her own phone number, is the ONLY thing that makes "
                f"the id honest"
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

    🔴 **And it cannot be closed the way the write side is.** A grant pins payload values
    (hub#1623), but only on a `command`: `crates/runtime/src/flows/grants.rs` refuses a `payload`
    on any other kind with `flow.invalid_grant_payload`, because `check_command_grant` is the one
    gate handed a payload and a restriction nothing applies is worse than none. Both links here
    are `query` grants. So there is nothing to pin, and taking the reads away instead would take
    cancelling with them.

    What closes it is moving the LOOKUP out of the model's hands. The kernel already has the
    shape: a `query` step (hub#954) is a deterministic read whose params are mapped by the
    DOCUMENT, not chosen by a model — and `{{input.from}}` is the phone WhatsApp itself vouched
    for. Resolve the customer there, and the only `customer_id` that exists in the run is the one
    the number belongs to. Four marks, each of them one edit away from being lost:

    * **the model is never handed the address book** — `DIRECTORY_QUERY` out of every `ai` step's
      `tools.queries`. This is the red the issue is: leave it in and every other mark here is
      decoration, because the model can resolve anybody by name whatever the prompt says;
    * **whoever can read a diary has a deterministic resolver BEFORE it** — a `kind: query` step
      over `DIRECTORY_QUERY` earlier in the document. «Earlier» is not pedantry: `steps.x` of a
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
    resolvers = _query_steps(doc, DIRECTORY_QUERY)

    # Mark 5, and the one that caught a real bug in this very commit: a resolver ANSWERS in
    # `{{steps.<id>.…}}`, and the braces are the whole mechanism. Written with one brace the
    # runtime never resolves it (`resolve_path` is only reached from `{{…}}`), so the model is
    # handed the literal text `{steps.find_customer.id}`, finds no id in it, and goes back to
    # deciding who this run is about — with every other mark here still green, because the step
    # LOOKS wired. The reservation templates have no diary read, so mark 4 does not cover them:
    # this one is owed by every resolver in every family.
    for index, step in enumerate(steps):
        if step.get("kind") != "query" or step.get("query") != DIRECTORY_QUERY:
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
                f"message named. Add a deterministic read of `{DIRECTORY_QUERY}` keyed on "
                f"`{{{{{TRUSTED_PHONE}}}}}` ahead of this step"
            )
            continue

        for _, resolver in earlier:
            rid = resolver.get("id")
            params = resolver.get("params") or {}
            if not params:
                problems.append(
                    f"{name} step `{rid}` resolves the customer with `{DIRECTORY_QUERY}` and "
                    f"passes NO params: that is the whole address book, and its first row is "
                    f"somebody. Key it on `{{{{{TRUSTED_PHONE}}}}}`"
                )
                continue
            for key, expr in sorted(params.items()):
                text = expr if isinstance(expr, str) else json.dumps(expr, sort_keys=True)
                if "{{steps." in text or text.startswith("steps."):
                    problems.append(
                        f"{name} step `{rid}` resolves the customer with `{DIRECTORY_QUERY}` and "
                        f"takes `{key}` from another step's output (`{text}`). If that step is an "
                        f"`ai` one, the model is choosing who this run is about again — the "
                        f"lookup moved, the hole did not. Key it on `{{{{{TRUSTED_PHONE}}}}}`"
                    )
            if not any(
                TRUSTED_PHONE in (expr if isinstance(expr, str) else "")
                for expr in params.values()
            ):
                problems.append(
                    f"{name} step `{rid}` resolves the customer with `{DIRECTORY_QUERY}` and "
                    f"never reads `{TRUSTED_PHONE}`: it is keyed on "
                    f"{json.dumps(params, sort_keys=True)}, so it answers about somebody the "
                    f"phone number never picked out. The trigger's own `from` is the only "
                    f"identity in this run WhatsApp vouched for"
                )

        prompt = prompt_of(step)
        if not any(f"steps.{s.get('id')}.id" in prompt for _, s in earlier):
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
    for trigger in whatsapp_triggers(doc):
        condition = trigger.get("filter") or {}
        for label, payload, wanted, why in MESSAGE_KINDS:
            try:
                got = _filter_matches(condition, {"event": payload})
            except _UnjudgeableFilter as e:
                problems.append(
                    f"{name} filters on `{e}`, an operator this battery has no faithful copy of, "
                    f"so it cannot say who this trigger wakes up for. Add it to "
                    f"`_clause_matches` from `eval()` in `crates/runtime/src/flows/def.rs` in the "
                    f"same commit"
                )
                break
            if got == wanted:
                continue
            problems.append(
                f"{name} {'ignores' if wanted else 'answers'} {label}: {why}. Its trigger filter "
                f"is {json.dumps(condition, sort_keys=True)}"
            )

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



DOCUMENT_RULES = (
    policy_problems,
    identified_cancellation_problems,
    identity_field_problems,
    silence_problems,
    mute_refusal_problems,
    undeclared_tool_problems,
    unordered_tool_problems,
    budget_problems,
    enum_value_problems,
    unattended_problems,
    hour_choice_problems,
    shipped_recipe_problems,
    unowned_table_problems,
    moving_problems,
    own_customer_only_problems,
    only_the_customer_problems,
)

# …and the registry itself is guarded, because it is the next place the same hole moves to. The
# ledger only demands the rules DOCUMENT_RULES names, so deleting a name from that tuple left the
# rule running, its cases passing and nothing requiring it to ever meet a real template again
# (whatsapp_inbox#61, mutant P4). Every rule `self_check()` proves has to be one `main()` is
# REQUIRED to apply, and that is asserted rather than assumed.
SELF_CHECKED_RULES = (
    policy_problems,
    identified_cancellation_problems,
    identity_field_problems,
    silence_problems,
    mute_refusal_problems,
    undeclared_tool_problems,
    unordered_tool_problems,
    budget_problems,
    enum_value_problems,
    unattended_problems,
    hour_choice_problems,
    shipped_recipe_problems,
    unowned_table_problems,
    moving_problems,
    own_customer_only_problems,
    only_the_customer_problems,
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
                "command": s.get("command"),
                "when": s.get("when"),
                "seconds": s.get("seconds"),
            }
            for s in doc.get("steps", [])
        ],
    }


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


def _ai_step(step_id, policy, commands, prompt="", on_reject=None, queries=()):
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
    return step


def _query_step(step_id, query=None, params=None):
    """The deterministic read (hub#954): the DOCUMENT maps the params, never the model."""
    step = {
        "id": step_id,
        "kind": "query",
        "query": DIRECTORY_QUERY if query is None else query,
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


def _fixture_doc(*steps):
    return {"schema_version": 1, "triggers": [], "steps": list(steps)}


# The name a mutant document is judged UNDER: the family is what buys the unattended exception, so
# every row carries one. `(label, file name, document, problems expected)`.
ATTENDED = "appointment-from-whatsapp.en.flow.json"
UNATTENDED = "appointment-from-whatsapp-unattended.en.flow.json"

POLICY_CASES = [
    (
        "a read inside a `manual` step is what hub#1595 made legal",
        ATTENDED,
        _fixture_doc(_ai_step("s", "manual", ["appointments.availability.slots"])),
        0,
    ),
    (
        "a write inside an `auto` step is still the dangerous direction",
        ATTENDED,
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
        "appointment-from-whatsapp-unattended-draft.en.flow.json",
        _fixture_doc(_ai_step("s", "auto", ["appointments.appointments.create"])),
        1,
    ),
    (
        "a write inside a `manual` step is the default, and the point of it",
        ATTENDED,
        _fixture_doc(_ai_step("s", "manual", ["appointments.appointments.create"])),
        0,
    ),
    (
        "a read inside an `auto` step is fine",
        ATTENDED,
        _fixture_doc(_ai_step("s", "auto", ["appointments.availability.slots"])),
        0,
    ),
    (
        "a step that only asks, feeding a step that acts, is the split whatsapp_inbox#55 removed",
        ATTENDED,
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
        ATTENDED,
        _fixture_doc(
            _ai_step("look", "auto", ["appointments.availability.slots"]),
            _ai_step("act", "manual", ["appointments.appointments.create"], "{{ steps.look.text }}"),
        ),
        1,
    ),
    (
        "a step that only asks and that nobody quotes is not the split",
        ATTENDED,
        _fixture_doc(
            _ai_step("look", "auto", ["appointments.availability.slots"]),
            _ai_step("act", "manual", ["appointments.appointments.create"]),
        ),
        0,
    ),
    (
        "asking and proposing in ONE step is the shape this repo now ships",
        ATTENDED,
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
        ATTENDED,
        _fixture_doc(
            _ai_step("book", "manual", ["appointments.appointments.create"]),
            _approval_step(),
            _notify_step(),
        ),
        0,
    ),
]


UNATTENDED_ES = "appointment-from-whatsapp-unattended.es.flow.json"
# The table families (whatsapp_inbox#60). A restaurant runs the same automation against
# `reservations`, so it inherits the same rules — including this one, under its own wording.
TABLE_ATTENDED = "reservation-from-whatsapp.en.flow.json"
TABLE_UNATTENDED = "reservation-from-whatsapp-unattended.en.flow.json"
TABLE_UNATTENDED_ES = "reservation-from-whatsapp-unattended.es.flow.json"

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
        ATTENDED,
        _fixture_doc(_ai_step("book", "manual", [BOOKING_COMMAND], "Book whatever fits best.")),
        0,
    ),
    (
        "a language this battery has no wording for is a document it cannot vouch for — a third "
        "translation adds its sentence to HOUR_RULE in the same commit, or it does not ship",
        "appointment-from-whatsapp-unattended.fr.flow.json",
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
        TABLE_ATTENDED,
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

_CHAIR_PAIR = {
    "appointment-from-whatsapp": {BOOKING_COMMAND},
    "appointment-from-whatsapp-unattended": {BOOKING_COMMAND},
}
_TABLE_ATTENDED = {"reservation-from-whatsapp": {TABLE_BOOKING_COMMAND}}
_TABLE_UNATTENDED = {"reservation-from-whatsapp-unattended": {TABLE_BOOKING_COMMAND}}

RECIPE_CASES = [
    (
        "what this module ships once whatsapp_inbox#60 lands: a pair of families for every "
        "booking the battery has a wording for",
        {**_CHAIR_PAIR, **_TABLE_ATTENDED, **_TABLE_UNATTENDED},
        0,
    ),
    (
        "the red whatsapp_inbox#60 IS: the table wording is pinned and no document anywhere books "
        "a table, so the restaurant that connects its WhatsApp is offered a hairdresser's recipes "
        "and nothing else",
        _CHAIR_PAIR,
        2,
    ),
    (
        "half the delivery: the restaurant that runs its WhatsApp with nobody watching can install "
        "the recipe, and the one that wants to read its bookings first has nothing",
        {**_CHAIR_PAIR, **_TABLE_UNATTENDED},
        1,
    ),
    (
        "the other half: the recipe exists and parks every table at 3 AM in an approval tray the "
        "restaurant that bought the unattended one does not open",
        {**_CHAIR_PAIR, **_TABLE_ATTENDED},
        1,
    ),
    (
        "a family that books something else does not cover the row: `customers.create` writes, and "
        "no customer ever sat at it",
        {**_CHAIR_PAIR, "reservation-from-whatsapp": {"customers.create"},
         "reservation-from-whatsapp-unattended": {"customers.create"}},
        2,
    ),
    (
        "and the row that started it all is judged the same way: delete the chair recipes and this "
        "rule says so, so it cannot be one that only ever fires for tables",
        {**_TABLE_ATTENDED, **_TABLE_UNATTENDED},
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
        TABLE_ATTENDED,
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
        ATTENDED,
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
        ATTENDED,
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
        "it can move and cannot look up what it is moving: `reschedule` takes no `channel` and no "
        "`customer_id`, so nothing downstream refuses another person's appointment",
        ATTENDED,
        _fixture_doc(
            _ai_step("propose", "manual", _MOVE_TOOLS, f"Move it. {MOVE_RULE['en']}")
        ),
        1,
    ),
    (
        "the sentence reworded away: cancelling and re-booking is still in the same hands, and it "
        "leaves the customer who asked to KEEP her hour with nothing when the second call fails",
        ATTENDED,
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
        ATTENDED,
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
        "the unattended family owes the OPPOSITE, and this is the shape it ships: it cannot move, "
        "and its prompt says so, so «change it to Thursday» is answered by a person",
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
        0,
    ),
    (
        "🔴 the regression this rule exists to stop: with nobody watching, moving is a write "
        "nothing can scope — `reschedule` takes no `customer_id` and its handler never checks "
        "whose appointment it is, so the id can be anybody's",
        UNATTENDED,
        _fixture_doc(
            _ai_step(
                "book",
                "auto",
                _MOVE_TOOLS,
                f"Move it. {MOVE_RULE['en']}",
                queries=_MOVE_QUERIES,
            )
        ),
        1,
    ),
    (
        "and it is the POLICY that decides, not the file name: a writer that forgot to say who "
        "approves it is treated as nobody watching, because that is the side that fails silently",
        ATTENDED,
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
        1,
    ),
    (
        "the sentence that sends her to a person, reworded away: she asks to move her hour and "
        "the model improvises — silence, or a SECOND appointment on top of the one she wanted",
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
        "a language this battery has no «not yet» wording for is a document it cannot vouch for "
        "on that side either",
        "appointment-from-whatsapp-unattended.fr.flow.json",
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
        "a step that cannot book owes nothing: the customer-record step writes, but not into the "
        "diary",
        ATTENDED,
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
_OWN_PHONE = {"f_phone": "+{{" + TRUSTED_PHONE + "}}"}
_DIARY = (OWNED_APPOINTMENTS_QUERY,)


def _own_customer_doc(prompt, queries, params=_OWN_PHONE, resolver_first=True):
    """The shipped shape, with one thing moved — whatever the row under test is about."""
    resolver = _query_step("resolve", params=params)
    reader = _ai_step("book", "auto", [BOOKING_COMMAND], prompt, queries=queries)
    return _fixture_doc(*((resolver, reader) if resolver_first else (reader, resolver)))


_BOOK_FOR_HER = "Book for {{steps.resolve.id}} and for nobody else."

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
        1,
    ),
    (
        "silent where nothing is owed: a step that reads no diary and holds no address book",
        ATTENDED,
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


# `(label, file name, document, problems expected)` — the mutants of «a customer, and only now».
ONLY_CUSTOMER_CASES = [
    (
        "the shape whatsapp_inbox#90 ships: the owner's echo and the backlog are both refused, "
        "and a core at the floor still wakes up",
        ATTENDED,
        _wa_doc(LIVE_INBOUND),
        0,
    ),
    (
        "the filter as it was: «anything with words in it» answers the owner's own reply AND "
        "every message of the 180-day backlog",
        ATTENDED,
        _wa_doc(TEXT_ONLY),
        2,
    ),
    (
        "who spoke, without when: the backlog still arrives",
        ATTENDED,
        _wa_doc({**TEXT_ONLY, "event.direction": {"neq": "outbound"}}),
        1,
    ),
    (
        "when, without who: the owner is still answered by her own automation",
        ATTENDED,
        _wa_doc({**TEXT_ONLY, "event.source": {"neq": "history"}}),
        1,
    ),
    (
        "🔴 `eq` reads right and is the regression: on a core at this module's declared floor the "
        "path is absent, `json_eq(Null, \"inbound\")` is false, and the automation is off with "
        "nothing said",
        ATTENDED,
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
        ATTENDED,
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
        ATTENDED,
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
        ATTENDED,
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
        ATTENDED,
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
        ATTENDED,
        _wa_doc({**LIVE_INBOUND, "event.direction": {"contains": "in"}}),
        1,
    ),
    (
        "🔴 the reply addressed by `event.contact` — the field that is RIGHT in an echo, and "
        "absent on a core at the floor, where it hands the query a `null`",
        ATTENDED,
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
        ATTENDED,
        _wa_doc(LIVE_INBOUND, steps=[_contact_notify()]),
        1,
    ),
    (
        "every notify step is judged, not the first: two replies wrongly addressed are two "
        "customers who get somebody else's message",
        ATTENDED,
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
        ATTENDED,
        {
            "schema_version": 1,
            "triggers": [{"kind": "event", "event": "sale.completed", "filter": {}}],
            "steps": [_notify_step()],
        },
        0,
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
    for label, props, expected in [
        ("the schema declares both fields", want, 0),
        (
            "`customer_id` is gone from the schema",
            {"appointments.appointments.cancel": {"appointment_id", "channel"}},
            1,
        ),
        ("the command's schema could not be read", {}, 0),
    ]:
        got_anchor = identity_field_problems("(self-check)", {}, props)
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


def self_check():
    """The mutants of the rules above, run every time, before any real document is opened."""
    problems = []
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
    validator = None
    if not HUB_SCHEMA.is_file():
        skipped.append(
            f"flow.schema.json not found at {HUB_SCHEMA} — the documents were NOT validated"
        )
    else:
        try:
            import jsonschema

            validator = jsonschema
        except ImportError:
            skipped.append(
                f"`jsonschema` is not installed — the documents were NOT validated against "
                f"{HUB_SCHEMA.name}; every other layer below still ran"
            )

    if validator is not None:
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

    # Which family books what, read once: `shipped_recipe_problems` judges the SET of
    # documents, and the set is not visible from any one of them.
    booked = booked_families((path, json.loads(path.read_text())) for path in docs)

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

        # 3a-bis-ii) …and a family that CALLS itself unattended really is (whatsapp_inbox#58): the
        # other half of the exception `policy_problems` grants it. Needs no manifest either.
        problems += applied(ledger, unattended_problems, path.name, doc)

        # 3a-bis-iii) …and, in that family, the step that can book still says in so many words that
        # it never picks the hour (whatsapp_inbox#58, reviewer mutant N2). Prose, pinned on purpose.
        problems += applied(ledger, hour_choice_problems, path.name, doc)

        # 3a-bis-iii-bis) …and every booking that wording exists for is one this module really
        # SHIPS, in both families (whatsapp_inbox#60). Needs no manifest: it reads `flows/`.
        problems += applied(ledger, shipped_recipe_problems, path.name, doc, booked)

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
            problems += applied(ledger, identity_field_problems, path.name, doc, identity_props)

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

        # The trigger this whole issue is about: a template that listens to something else is a
        # different product wearing the same file name.
        events = {
            t.get("event") for t in doc.get("triggers", []) if t.get("kind") == "event"
        }
        if "hub.whatsapp.message_received" not in events:
            problems.append(
                f"{path.name} does not trigger on `hub.whatsapp.message_received`: {sorted(events)}"
            )

    # 3c) …and every rule above actually MET every document that reached this far. Waived only for
    # the layer that was skipped out loud (no manifests next door → no `policy_problems`).
    waived = (
        {
            policy_problems.__name__,
            undeclared_tool_problems.__name__,
            enum_value_problems.__name__,
            identity_field_problems.__name__,
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

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

And because these rules only ever run over documents that are already correct, the battery mutates
its OWN rules first (`self_check`) — a blinded rule would otherwise stay green forever.

Usage: tests/flow_templates.test.py   (exit 0 = green)
"""

import json
import pathlib
import sys

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


def needed_grants(doc):
    """Exactly the grants this document needs, as `(kind, value)` pairs."""
    needed = set()
    for step in doc.get("steps", []):
        if step.get("kind") == "ai":
            tools = step.get("tools", {})
            for q in tools.get("queries", []):
                needed.add(("query", q))
            for c in tools.get("commands", []):
                needed.add(("command", c))
        elif step.get("kind") == "notify":
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
                quoted = path[len("steps.") :].split(".")[0].strip()
                if quoted and quoted != step.get("id"):
                    out.add(quoted)
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
            if policy == "auto" and not answers:
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
    """
    steps = doc.get("steps", [])
    writing = writing_ai_steps(doc)
    if not writing:
        return []
    last = writing[-1]
    if any(s.get("kind") == "notify" for s in steps[last + 1 :]):
        return []
    return [
        f"{name} step `{steps[last].get('id')}` can book something and NO `notify` comes after it: "
        f"the customer is told «we will confirm shortly» and then never hears again, whoever "
        f"approves. The run resumes after an approval (`decide_flow_approval` completes the step "
        f"with `Done`), so a `notify` written after this step covers both endings — booked, and "
        f"nothing found"
    ]


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


DOCUMENT_RULES = (policy_problems, silence_problems, undeclared_tool_problems)

# …and the registry itself is guarded, because it is the next place the same hole moves to. The
# ledger only demands the rules DOCUMENT_RULES names, so deleting a name from that tuple left the
# rule running, its cases passing and nothing requiring it to ever meet a real template again
# (whatsapp_inbox#61, mutant P4). Every rule `self_check()` proves has to be one `main()` is
# REQUIRED to apply, and that is asserted rather than assumed.
SELF_CHECKED_RULES = (policy_problems, silence_problems, undeclared_tool_problems)


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


def _ai_step(step_id, policy, commands, prompt=""):
    return {
        "id": step_id,
        "kind": "ai",
        "policy": policy,
        "prompt": prompt,
        "tools": {"commands": list(commands)},
    }


def _fixture_doc(*steps):
    return {"schema_version": 1, "triggers": [], "steps": list(steps)}


POLICY_CASES = [
    (
        "a read inside a `manual` step is what hub#1595 made legal",
        _fixture_doc(_ai_step("s", "manual", ["appointments.availability.slots"])),
        0,
    ),
    (
        "a write inside an `auto` step is still the dangerous direction",
        _fixture_doc(_ai_step("s", "auto", ["appointments.appointments.create"])),
        1,
    ),
    (
        "a write inside a `manual` step is the default, and the point of it",
        _fixture_doc(_ai_step("s", "manual", ["appointments.appointments.create"])),
        0,
    ),
    (
        "a read inside an `auto` step is fine",
        _fixture_doc(_ai_step("s", "auto", ["appointments.availability.slots"])),
        0,
    ),
    (
        "a step that only asks, feeding a step that acts, is the split whatsapp_inbox#55 removed",
        _fixture_doc(
            _ai_step("look", "auto", ["appointments.availability.slots"]),
            _ai_step("act", "manual", ["appointments.appointments.create"], "{{steps.look.text}}"),
        ),
        1,
    ),
    (
        "the same split quoted with spaces inside the braces — `{{ steps.look.text }}` — is still "
        "the split: the hub trims the path before resolving it (`render_template`), so the "
        "guard has to read it the way the hub does",
        _fixture_doc(
            _ai_step("look", "auto", ["appointments.availability.slots"]),
            _ai_step("act", "manual", ["appointments.appointments.create"], "{{ steps.look.text }}"),
        ),
        1,
    ),
    (
        "a step that only asks and that nobody quotes is not the split",
        _fixture_doc(
            _ai_step("look", "auto", ["appointments.availability.slots"]),
            _ai_step("act", "manual", ["appointments.appointments.create"]),
        ),
        0,
    ),
    (
        "asking and proposing in ONE step is the shape this repo now ships",
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


SILENCE_CASES = [
    (
        "an automation that books and then says so is the whole point",
        _fixture_doc(
            _ai_step("book", "manual", ["appointments.appointments.create"]),
            _notify_step(),
        ),
        0,
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
    for label, doc, expected in SILENCE_CASES:
        got = silence_problems("(self-check)", doc)
        if len(got) != expected:
            problems.append(
                f"the battery's own «say something back» rule is wrong — {label}: expected "
                f"{expected} problem(s), got {len(got)}: {got}"
            )
    for label, doc, expected in TOOL_CASES:
        got = undeclared_tool_problems("(self-check)", doc, _KNOWN_OPS)
        if len(got) != expected:
            problems.append(
                f"the battery's own «the prompt only orders what it was handed» rule is wrong — "
                f"{label}: expected {expected} problem(s), got {len(got)}: {got}"
            )
    for label, doc, expected in POLICY_CASES:
        got = policy_problems("(self-check)", doc, _FIXTURE_COMMANDS, _FIXTURE_READS)
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

        # 3a-ter) …and every tool its prompts ORDER was actually handed over (whatsapp_inbox#61).
        # Needs the manifests: «is this a tool name or is it prose» is a question only they answer.
        if contracts is not None:
            problems += applied(
                ledger, undeclared_tool_problems, path.name, doc, contracts[0] | contracts[1]
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
        {policy_problems.__name__, undeclared_tool_problems.__name__}
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

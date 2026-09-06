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


def command_is_read_only(cdef):
    """Does this command ANSWER a question rather than change the business?

    Two independent signals from the owner's manifest, and BOTH have to hold, because getting this
    wrong in the permissive direction is the expensive direction — it would let a write into a
    `policy: "auto"` step, which is a model writing to the salon's database at 3 AM with nobody
    looking (ADR-0283 D3, the reason `manual` is the default):

    * it publishes NO domain event (`emit`) — a state change the rest of the hub must hear about
      is a write by definition; and
    * its `permission` is a `view_*` one — the permission a screen asks for to READ.

    Neither alone is enough, and that is measured on the manifests next door rather than assumed:
    `customers.bulk_create` declares no `emit` at all and is plainly a write, and it is the
    `customers.add_customer` permission that says so.

    Its limit, stated rather than hidden: a command that both published no event and asked only for
    a `view_*` permission while writing would pass here. That is a defect in ITS manifest — an
    unannounced write wearing a read's permission — and this battery cannot see it from the outside.
    """
    if cdef.get("emit"):
        return False
    permission = cdef.get("permission")
    if not isinstance(permission, str):
        return False
    return permission.rsplit(".", 1)[-1].startswith("view_")


def ai_steps(doc):
    """`(step id, policy, [command names])` for every `ai` step that may propose a write."""
    out = []
    for step in doc.get("steps", []):
        if step.get("kind") != "ai":
            continue
        commands = ((step.get("tools") or {}).get("commands")) or []
        out.append((step.get("id"), step.get("policy") or "manual", list(commands)))
    return out


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


def main():
    problems, skipped = [], []

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

    for path in docs:
        doc = json.loads(path.read_text())

        # 2) The grants, both ways.
        gpath = grants_of(path)
        if not gpath.is_file():
            problems.append(
                f"{path.name} has no `{gpath.name}`: a document without its grants is a flow that saves and then dies with `flow.grant_denied`"
            )
            continue
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

        # 3a) A command a step declares is a WRITE, and `policy` is what decides its fate.
        #
        # `flow.schema.json` freezes both halves of this and they are the same sentence read twice:
        # `tools.commands` is «escrituras que el modelo puede PROPONER», and `policy: "manual"` —
        # the default, and this template's — means the proposal «se convierte en una fila de
        # `_flow_approvals` y el turno TERMINA». So a READ-ONLY operation parked in `tools.commands`
        # of a manual step is not a lookup at all: the model asks what hours are free, the run stops,
        # and a person is handed an approval card for a question. That is whatsapp_inbox#52 in its
        # next incarnation, and nothing else in this repo would notice — `appointments` turned
        # `availability.slots`, `.check` and `.day_opening` into commands precisely because they need
        # a WASM handler to answer with the authority the booking door uses, and their names did not
        # change when their kind did.
        #
        # The other direction is the dangerous one and is checked just as hard: a step that runs its
        # commands without asking (`policy: "auto"`) may only declare operations that answer. A write
        # in there is the model booking, charging or deleting at 3 AM with nobody looking, which is
        # the entire reason `manual` is the default (ADR-0283 D3).
        if commands_def is not None:
            for step_id, policy, names in ai_steps(doc):
                for name in names:
                    target = commands_def.get(name)
                    if target is None:
                        continue  # already reported above as a name no module declares
                    _, cdef = target
                    if policy == "manual" and command_is_read_only(cdef):
                        problems.append(
                            f"{path.name} step `{step_id}` declares `{name}` in `tools.commands` "
                            f"under `policy: manual`, but that operation only READS. Under `manual` "
                            f"the first command call becomes an `_flow_approvals` row and the turn "
                            f"ends, so the model never gets the answer and a person is asked to "
                            f"approve a question. A read the model has to act on belongs in a step "
                            f"with `policy: auto`"
                        )
                    if policy == "auto" and not command_is_read_only(cdef):
                        problems.append(
                            f"{path.name} step `{step_id}` declares `{name}` in `tools.commands` "
                            f"under `policy: auto`, and that operation WRITES. `auto` runs it in "
                            f"the turn, unattended: a write with nobody looking is exactly what "
                            f"`manual` is the default for"
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

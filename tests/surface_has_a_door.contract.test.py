#!/usr/bin/env python3
"""Everything this module DECLARES has to have a door somebody can walk through (whatsapp_inbox#29).

A module manifest is a promise: a permission gates something, a command is reachable, a query feeds
a screen. When it does not, the promise is worse than a missing feature — it reads as done. The
audit of 2026-08-19 found the module consuming **3 of the 7 queries it declares**, six commands with
no caller at all, and one permission (`send_message`) handed to three roles while **nothing in the
manifest referenced it**: an audit of "can this employee reply?" answered yes, and the product could
not reply at all.

So this gate asks three questions of the manifest, and answers each from the code, never from
memory:

1. **Every declared permission gates something.** A permission no query and no command names is not
   a restriction, it is a label on an empty box.
2. **Every public query and command has a caller.** The callers are read from
   `.erplora/contracts.json`, which `erplora build` extracts from the Web Components by LITERAL
   (ADR-0127) — so this cannot be satisfied by a name behind a constant, and it stays true on its
   own as the UI changes.
3. **What has no caller says why, out loud.** `PENDING` below is the list of surface that is
   knowingly unreachable, each with the issue that will close it. It is not an escape hatch: it is
   the debt, written down, and a new name may only be added with a reason a reader can check.

The doors that are NOT a screen are recognised as what they are, not waved through:
  * a command named by `events.listen` — the relay calls it,
  * a command a WASM handler returns as an intention — the runtime calls it,
  * a query the manifest hands to the SHELL to call — `billing.usage.query`, `widgets.*.query`,
    `protects[].settings_query` / `.guard_query`. These have no Web Component of ours because the
    screen belongs to the Hub, not to us: the module DECLARES the name and the shell resolves it
    (whatsapp_inbox#131). Declaring it IS the door, and getting the name wrong is caught by the
    manifest's own schema, not here.
  * a command a RECIPE of ours calls — `flows/*.flow.json` ships with the module (hub#1654) and its
    `command` steps are run by the flow executor, which is a caller as real as a button. It counts
    only when the family's `<family>.grants.json` grants it too: a step without its grant is
    refused at run time (`flows/grants.rs::check_command_grant`), so the step ALONE is a door that
    does not open (whatsapp_inbox#133). The same goes for a query a recipe's `query` step reads
    under a `query` grant (whatsapp_inbox#76): the executor runs it, gated by the grant.
  * an `internal: true` command, or one prefixed `_`, which no caller outside the module may reach.

Usage: tests/surface_has_a_door.contract.test.py   (exit 0 = green). No Postgres, no Docker.
"""

import json
import pathlib
import re
import sys

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())
CONTRACTS = json.loads((MODULE_DIR / ".erplora/contracts.json").read_text())

# Surface that is deliberately unreachable from a screen today, and why. Each entry names the issue
# that closes it. 🔴 Only ever add a line here with a reason a reader can verify — an entry without
# one turns this gate into a rubber stamp.
PENDING = {
    "whatsapp_inbox.messages.ingest": (
        "channel intake point, not a user action: the hub's inbound pipeline calls it with the "
        "`manage_connections` permission (see docs/overview.md)"
    ),
    "whatsapp_inbox.requests.ingest": (
        "same intake point, one step later: the caller hands over the payload the LLM already "
        "parsed (WASM-TODO.md §3)"
    ),
    # The three below lost their screen when Settings became the three-step screen (whatsapp_inbox
    # #123, ADR-0470). They are not orphans by accident: the ADR names where each one goes, and
    # `check_pending_is_still_pending` takes the line out again the day it gets a caller.
    "whatsapp_inbox.settings.get": (
        "the three-step screen writes NOT ONE column of `whatsapp_inbox` (ADR-0470 §3: the single "
        "decision is `appointments.settings.set_auto_confirm_online`, in the module that owns the "
        "diary), so the read that fed the old form has no screen left. What survives of the "
        "singleton row is `free_tier_monthly_limit` — written by `_quota.set`, never by a person — "
        "and `account_mode`; whatsapp_inbox#127 reduces both operations to exactly that and drops "
        "the dead columns"
    ),
    "whatsapp_inbox.settings.upsert": (
        "the other half of the same retreat: the «Guardar» button went out with the paragraphs it "
        "saved (ADR-0470). Reduced to `free_tier_monthly_limit` + `account_mode` by "
        "whatsapp_inbox#127 — and the quota half of that is already `_quota.set`'s job, which is "
        "why `settings_quota_owner.pg.test.py` exists"
    ),
}


def declared_permissions():
    return list(MANIFEST.get("permissions", []))


def permissions_in_use():
    """Every permission some query or command actually gates."""
    used = set()
    for kind in ("queries", "commands"):
        for spec in MANIFEST.get(kind, {}).values():
            if spec.get("permission"):
                used.add(spec["permission"])
    return used


def handler_intentions():
    """Command names a WASM handler returns as intentions — the runtime is their caller."""
    source = (MODULE_DIR / "handler/src/lib.rs").read_text()
    return set(re.findall(r'"(whatsapp_inbox\.[a-z0-9_.]+)"', source))


def recipe_callers():
    """Commands and queries our own shipped recipes call — the flow executor is their caller.

    Both halves are required. The `command` step names it, and the family's grants file has to
    grant it: the executor checks the grant before it runs the step, so a step whose grant is
    missing links nothing and would otherwise read here as a door that opens.
    """
    called = set()
    for recipe in sorted((MODULE_DIR / "flows").glob("*.flow.json")):
        family = recipe.name.split(".")[0]
        grants_path = MODULE_DIR / "flows" / f"{family}.grants.json"
        if not grants_path.exists():
            continue
        granted = {
            (g.get("kind"), g.get("value"))
            for g in json.loads(grants_path.read_text()).get("grants", [])
        }
        for step in json.loads(recipe.read_text()).get("steps", []):
            kind = step.get("kind")
            if kind in ("command", "query") and (kind, step.get(kind)) in granted:
                called.add(step[kind])
    return called


def listener_targets():
    return {
        spec["command"]
        for spec in MANIFEST.get("events", {}).get("listen", {}).values()
    }


def shell_doors():
    """Query names the manifest hands to the Hub's SHELL, which is their caller.

    The shell reads the raw `module.json` and resolves these by name; the module ships no Web
    Component for them on purpose, because the screen is the Hub's (the «Plan» tab is synthetic —
    `ModuleView.vue`, id `__plan__`). Without this, declaring the counter would leave
    `usage.get` looking as unreachable as it did when nothing pointed at it at all.
    """
    doors = set()

    usage = MANIFEST.get("billing", {}).get("usage")
    if usage and usage.get("query"):
        doors.add(usage["query"])

    for widget in MANIFEST.get("widgets", {}).values():
        if widget.get("query"):
            doors.add(widget["query"])

    for guard in MANIFEST.get("protects", []):
        for field in ("settings_query", "guard_query"):
            if guard.get(field):
                doors.add(guard[field])

    return doors


def public_names():
    """Public queries and commands: the ones a caller outside this module could reach."""
    out = []
    for kind in ("queries", "commands"):
        for name, spec in MANIFEST.get(kind, {}).items():
            if spec.get("internal"):
                continue
            # `module._thing` is private by convention and the installer treats it as such.
            if name.rsplit(".", 1)[-1].startswith("_") or "._" in name:
                continue
            if re.search(r"\._[a-z]", name):
                continue
            out.append((kind, name))
    return out


def consumed():
    c = CONTRACTS.get("consumes", {})
    return (
        set(c.get("queries", []))
        | set(c.get("optional_queries", []))
        | set(c.get("commands", []))
    )


def check_every_permission_gates_something():
    problems = []
    used = permissions_in_use()
    for permission in declared_permissions():
        if permission in used:
            continue
        problems.append(
            f"`{permission}` is declared (and handed to roles) but NO query and NO command names "
            "it: an audit of who can do this answers yes, and there is nothing to do. Either a "
            "query/command gates on it, or it comes out of `permissions` and `role_permissions`"
        )
    return problems


def check_every_role_permission_exists():
    """A role cannot be given a permission the module does not declare."""
    problems = []
    declared = set(declared_permissions())
    for role, granted in MANIFEST.get("role_permissions", {}).items():
        for permission in granted:
            if permission == "*" or permission in declared:
                continue
            problems.append(
                f"role `{role}` is granted `{permission}`, which `permissions` does not declare"
            )
    return problems


KIND_LABEL = {"queries": "query", "commands": "command"}


def check_every_public_name_has_a_caller():
    problems = []
    callers = (
        consumed() | handler_intentions() | listener_targets() | shell_doors() | recipe_callers()
    )
    for kind, name in public_names():
        if name in callers or name in PENDING:
            continue
        problems.append(
            f"{KIND_LABEL[kind]} `{name}` has NO caller: it is not consumed by any Web Component "
            "(`.erplora/contracts.json`), no listener runs it and no handler returns it. Expose it "
            "in the UI, or retire it from the manifest — surface with no door reads as a feature "
            "that exists"
        )
    return problems


def check_pending_is_still_pending():
    """A `PENDING` entry that got its screen is stale bookkeeping: it must come out."""
    problems = []
    callers = (
        consumed() | handler_intentions() | listener_targets() | shell_doors() | recipe_callers()
    )
    declared = {name for _kind, name in public_names()}
    for name, reason in PENDING.items():
        if name not in declared:
            problems.append(
                f"`{name}` is listed as pending but the manifest no longer declares it — delete "
                "the line"
            )
        elif name in callers:
            problems.append(
                f"`{name}` is listed as pending ({reason}) but it DOES have a caller now — delete "
                "the line, the debt is paid"
            )
    return problems


def check_the_check_reaches_the_manifest():
    """A gate that scans an empty set passes for the wrong reason."""
    problems = []
    if len(public_names()) < 8:
        problems.append(
            f"only {len(public_names())} public names found: the manifest moved and this gate "
            "stopped guarding"
        )
    if not consumed():
        problems.append(
            "`.erplora/contracts.json` lists no consumed name — it is stale or was not built, and "
            "every name would look unreachable"
        )
    return problems


def main():
    problems = []
    problems += check_the_check_reaches_the_manifest()
    problems += check_every_permission_gates_something()
    problems += check_every_role_permission_exists()
    problems += check_every_public_name_has_a_caller()
    problems += check_pending_is_still_pending()

    for problem in problems:
        print(f"FAIL  {problem}")
    if problems:
        print(
            f"\n{len(problems)} promise(s) of the manifest that the code does not keep"
        )
        return 1

    print(
        f"OK: {len(declared_permissions())} permission(s) gate something, "
        f"{len(public_names())} public name(s) have a caller "
        f"({len(PENDING)} knowingly pending, each with its reason)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

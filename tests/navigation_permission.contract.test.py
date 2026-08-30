#!/usr/bin/env python3
"""Every tab says who it is for, or the menu shows a door that opens on a 403 (hub#1052).

WHY THIS FILE EXISTS. Until hub#1052 a `navigation[]` entry had nowhere to write «this tab is of
the admin»: `module.schema.json` items were closed over {id,label,icon,component,chrome,actions},
so `/api/navigation` served EVERY tab to EVERY user and the employee discovered the limit by
banging into the 403 of the query behind it. This module's own `role_permissions` makes that
concrete: `manager` and `employee` never hold `whatsapp_inbox.manage_settings`, so the Templates
and Settings tabs were two guaranteed 403s on their menu — painted as if they worked.

The field is not the door: the runtime re-validates the query/command of the screen on every
call. It is not OFFERING the door to someone who cannot open it, which is all a menu can honestly
do. Absent still means visible-to-all (every published manifest predates the field), so each of
this module's four tabs has to declare it explicitly.

WHAT THIS PINS, per tab:

  1. the entry carries a `permission` at all;
  2. that permission is one THIS module declares (not another module's, not the core's);
  3. it is the permission the tab's own screen needs — the one its PRIMARY query gates — so the
     menu and the door cannot disagree about who may enter. The mapping is written here as the
     contract, from the query the screen binds first (the WC's first `queryPage`/`query` call):
       inbox     → conversations.list → view_conversation
       requests  → requests.list      → view_request
       templates → templates.list     → manage_settings
       settings  → settings.get       → manage_settings

Usage: tests/navigation_permission.contract.test.py   (exit 0 = green). No Postgres, no Docker.
"""

import json
import pathlib
import sys

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())

# Tab → the query its screen loads first (the reason the tab exists), taken from the WC source.
# The screen's first read names the surface the tab is FOR; its `permission` in the manifest is
# the gate the runtime enforces on that read.
TAB_TO_PRIMARY_QUERY = {
    "inbox": ("erp-whatsapp-inbox-inbox", "whatsapp_inbox.conversations.list"),
    "requests": ("erp-whatsapp-inbox-requests", "whatsapp_inbox.requests.list"),
    "templates": ("erp-whatsapp-inbox-templates", "whatsapp_inbox.templates.list"),
    "settings": ("erp-whatsapp-inbox-settings", "whatsapp_inbox.settings.get"),
}

failures: list[str] = []


def component_source(component: str) -> str:
    base = MODULE_DIR / "ui" / "components" / component / f"{component}.ts"
    return base.read_text() if base.exists() else ""


def main() -> int:
    print("· every navigation tab declares the permission that opens it (hub#1052)")
    declared_permissions = set(MANIFEST.get("permissions", []))
    queries = MANIFEST.get("queries", {})
    entries = {entry["id"]: entry for entry in MANIFEST.get("navigation", [])}

    for tab, (component, primary_query) in TAB_TO_PRIMARY_QUERY.items():
        entry = entries.get(tab)
        if entry is None:
            failures.append(f"the `{tab}` tab disappeared from `navigation` — rewrite this gate")
            continue

        permission = entry.get("permission")
        if not permission:
            failures.append(
                f"`navigation[{tab}]` declares no `permission`: `/api/navigation` serves it to "
                "every user, and anyone without the screen's own permission lands on a 403 the "
                "menu itself offered (hub#1052)"
            )
            continue
        if permission not in declared_permissions:
            failures.append(
                f"`navigation[{tab}].permission` is `{permission}`, which this module does not "
                "declare in `permissions`"
            )
            continue

        # The menu and the door must agree: the tab's permission is the one its primary query
        # gates. A tab declared more permissive than its screen is the 403 all over again; one
        # declared stricter hides a screen people could use.
        query_permission = queries.get(primary_query, {}).get("permission")
        if permission != query_permission:
            failures.append(
                f"`navigation[{tab}].permission` is `{permission}` but the tab's primary query "
                f"`{primary_query}` gates `{query_permission}` — the menu and the door disagree"
            )
            continue

        # And the primary query is REALLY the screen's first read — otherwise the mapping above
        # went stale when the screen changed.
        if primary_query not in component_source(component):
            failures.append(
                f"`{component}` no longer calls `{primary_query}`: the tab→query mapping of this "
                "gate is stale, rewrite it"
            )
            continue
        print(f"  ok: `{tab}` opens with `{permission}` (the one `{primary_query}` gates)")

    # Absent = visible-to-all is the field's contract for PRE-EXISTING manifests; this module
    # has no tab that is honestly for everybody (the two reads are permission-gated), so a fifth
    # entry without a permission would be a decision somebody made — and it deserves to be made
    # here, out loud, not by omission.
    for tab in entries.keys() - TAB_TO_PRIMARY_QUERY.keys():
        if not entries[tab].get("permission"):
            failures.append(
                f"`navigation[{tab}]` is unknown to this gate and declares no `permission`: add "
                "the mapping (and the reason) or the permission"
            )

    if failures:
        print(f"\nFAIL ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK: the four tabs say who they are for; nobody is offered a 403")
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
this module's three tabs has to declare it explicitly.

WHAT THIS PINS, per tab:

  1. the entry carries a `permission` at all;
  2. that permission is one THIS module declares (not another module's, not the core's);
  3. it is the permission the tab's own screen needs — the one its PRIMARY query gates — so the
     menu and the door cannot disagree about who may enter. The mapping is written here as the
     contract, from the query the screen binds first (the WC's first `queryPage`/`query` call):
       inbox     → conversations.list → view_conversation
       requests  → requests.list      → view_request

🔴 AND ONE TAB IS NO LONGER GATED BY A QUERY OF THIS MODULE (whatsapp_inbox#123, ADR-0470). The
Settings screen used to open on `whatsapp_inbox.settings.get`, and that read is gone: what it does
first now is ask the KERNEL what it has already built from this module's families
(`GET /api/hub/flows/templates`, hub#1677). That route carries `auth:admin` and NO capability, so
the permission this module declares on the tab cannot be checked against a query's `permission` any
more — there is no query. Checking it against nothing would have been the honest-looking way to
turn this gate into a rubber stamp for that tab, so it is checked against the thing that actually
decides who gets in: `role_permissions`. If a role that the kernel will refuse (anything that is not
an admin) were offered the tab, that is the hub#1052 failure exactly, one layer over — a door in the
menu that opens on a 403 nobody warned about.

  4. so for a KERNEL-GATED tab: the screen really calls the kernel door (the mapping is not stale),
     the tab's permission is held by the admin roles and by NOBODY else, and it is held by at least
     one role — a permission no role has is a tab nobody can open.

🪦 The `templates` tab is gone from `navigation` (ADR-0470 §5): the Meta templates are folded into
the Settings screen instead of being a fourth tab on the owner's way. A screen that loses its tab
and is embedded NOWHERE is dead code that still ships, so the mapping it used to have is replaced by
`EMBEDDED_SCREENS`, which pins that it is still reachable from a shipped screen.

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
}

# Tab → (screen, the kernel call it opens on, the permission the menu declares). See §4 above: the
# check is against `role_permissions`, because there is no query of this module to check against.
TAB_TO_KERNEL_DOOR = {
    "settings": (
        "erp-whatsapp-inbox-settings",
        "activateTemplate",
        "whatsapp_inbox.manage_settings",
    ),
}

# The roles the kernel's `auth:admin` lets through. `owner` is not listed in `role_permissions` on
# purpose — the runtime holds it above `admin` — so what this pins is the roles this MODULE may
# hand the permission to.
ADMIN_ROLES = {"admin"}

# Screens with no tab of their own: each must be embedded by a screen that has one, or it is code
# that ships to every hub and can never be opened.
EMBEDDED_SCREENS = {
    "erp-whatsapp-inbox-templates": "erp-whatsapp-inbox-settings",
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
            failures.append(
                f"the `{tab}` tab disappeared from `navigation` — rewrite this gate"
            )
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
        print(
            f"  ok: `{tab}` opens with `{permission}` (the one `{primary_query}` gates)"
        )

    # The kernel-gated tab: no query of this module decides who gets in, so `role_permissions` is
    # what has to agree with the kernel's `auth:admin`.
    role_permissions = MANIFEST.get("role_permissions", {})
    for tab, (
        component,
        kernel_call,
        expected_permission,
    ) in TAB_TO_KERNEL_DOOR.items():
        entry = entries.get(tab)
        if entry is None:
            failures.append(
                f"the `{tab}` tab disappeared from `navigation` — rewrite this gate"
            )
            continue

        permission = entry.get("permission")
        if permission != expected_permission:
            failures.append(
                f"`navigation[{tab}].permission` is `{permission}`, and this tab opens on a kernel "
                f"route that only an admin may call: it has to declare `{expected_permission}`, "
                "the permission this module gives to admins alone"
            )
            continue
        if permission not in declared_permissions:
            failures.append(
                f"`navigation[{tab}].permission` is `{permission}`, which this module does not "
                "declare in `permissions`"
            )
            continue

        # The mapping is not stale: the screen really does open on the kernel door.
        if kernel_call not in component_source(component):
            failures.append(
                f"`{component}` no longer calls `{kernel_call}`: this tab is not kernel-gated any "
                "more, so checking it against `role_permissions` proves nothing — move it back to "
                "`TAB_TO_PRIMARY_QUERY` with the query it opens on now"
            )
            continue

        # …and nobody the kernel will refuse is offered the door. `*` is a role holding everything.
        holders = {
            role
            for role, granted in role_permissions.items()
            if "*" in granted or permission in granted
        }
        if not holders:
            failures.append(
                f"no role in `role_permissions` holds `{permission}`, so the `{tab}` tab is "
                "offered to nobody: the screen ships and cannot be opened"
            )
            continue
        if holders - ADMIN_ROLES:
            failures.append(
                f"`role_permissions` gives `{permission}` to {sorted(holders - ADMIN_ROLES)}, but "
                f"the `{tab}` screen opens on a kernel route that answers `forbidden` to anyone "
                "who is not an admin: the menu would offer them a door onto a 403, which is the "
                "hub#1052 failure this gate exists for"
            )
            continue
        print(
            f"  ok: `{tab}` opens on the kernel's `{kernel_call}` and is offered to "
            f"{sorted(holders)} alone"
        )

    # A screen that lost its tab has to be embedded somewhere, or it ships unreachable.
    for screen, host in EMBEDDED_SCREENS.items():
        if screen in entries or any(
            e.get("component") == screen for e in entries.values()
        ):
            failures.append(
                f"`{screen}` has a tab of its own again: either drop it from `EMBEDDED_SCREENS` "
                "and give it a row in the mappings above, or the owner has the same screen in two "
                "places"
            )
        elif f"<{screen}>" not in component_source(host):
            failures.append(
                f"`{screen}` has no tab and `{host}` does not embed it either, so it ships to "
                "every hub and nothing can open it: embed it, or stop shipping the screen"
            )
        else:
            print(f"  ok: `{screen}` has no tab of its own and `{host}` embeds it")

    # Absent = visible-to-all is the field's contract for PRE-EXISTING manifests; this module
    # has no tab that is honestly for everybody (the two reads are permission-gated), so a fifth
    # entry without a permission would be a decision somebody made — and it deserves to be made
    # here, out loud, not by omission.
    for tab in entries.keys() - TAB_TO_PRIMARY_QUERY.keys() - TAB_TO_KERNEL_DOOR.keys():
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
    print("\nOK: every tab says who it is for; nobody is offered a 403")
    return 0


if __name__ == "__main__":
    sys.exit(main())

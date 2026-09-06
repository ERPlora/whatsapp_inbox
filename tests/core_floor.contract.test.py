#!/usr/bin/env python3
"""This module says WHICH hub it needs, so an old one refuses it instead of failing mute (#62).

WHY THIS FILE EXISTS. The appointment automation this module ships (`flows/`) leans on a kernel
behaviour that landed in ERPlora/hub#1595: a command that only ANSWERS runs inside the turn
whatever the policy says. On a hub without it the first availability read of `propose_appointment`
turns into a row of `_flow_approvals` and the turn ends, so the owner gets a card asking them to
approve «check availability» — which is not a decision anybody can take — and the appointment is
never proposed. Nothing throws, nothing warns at install time, and the business finds out when a
customer is left without an appointment.

The manifest is the only place that can say no in time. `compatibility.min_erplora_version` is read
by the runtime (`Manifest::load` → `require_core_version`, hub#521): a core below the declared floor
refuses the install with `core_version_too_old` — "the module `x` needs a newer version of your
terminal … update the hub and install it again" — instead of half-landing. Until #62 this module
declared nothing, so every hub took it, and `flows/README.md` carried the requirement as prose:
documentation is not a guard.

WHAT THIS PINS:

  1. the manifest declares a core floor AT ALL (deleting it brings the mute failure back);
  2. the floor is a version the hub can compare against — an unreadable one is refused too
     (`ManifestCoreFloorUnreadable`), so a typo would brick the install rather than loosen it;
  3. it is not below the kernel floor measured below;
  4. and that measurement is RE-RUN here against the neighbouring hub checkout instead of trusted:
     the marker has to be present at the declared tag AND absent at the tag before the kernel
     floor. A control that cannot tell the two apart would pass no matter what the floor said.

THE KERNEL FLOOR, MEASURED (2026-09-06, `crates/server/src/agent_runner.rs` per tag):

  | ref      | `answers_only` |
  |----------|----------------|
  | v1.1.13  | absent         |
  | v1.1.14  | absent         |
  | v1.1.15  | present (x5)   |

So `v1.1.15` is the first release that carries hub#1595. Raising the floor later is fine (check 3
is a floor, not an equality); lowering it below 1.1.15 is the bug this file exists to catch.

Usage: tests/core_floor.contract.test.py   (exit 0 = green). No Postgres, no Docker.
"""

import json
import pathlib
import re
import subprocess
import sys

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())

# The oldest hub that can run this module's automation, and the evidence for that number.
KERNEL_FLOOR = (1, 1, 15)
# The marker of ERPlora/hub#1595 in the file that decides whether a tool call waits for approval.
KERNEL_MARKER = ("crates/server/src/agent_runner.rs", "answers_only")
# The last release WITHOUT it — the negative the control has to be able to see.
KERNEL_FLOOR_MINUS_ONE = "v1.1.14"
# Sibling checkout of ERPlora/hub in the monorepo (`modules-workspace/modules/<id>` → root).
HUB_CHECKOUT = MODULE_DIR.parent.parent.parent / "hub"

failures: list[str] = []


def triple(value: str) -> tuple[int, int, int] | None:
    """`x.y.z` as the runtime parses it (`manifest::version_triple`), or `None`."""
    match = re.fullmatch(r"\s*(\d+)\.(\d+)\.(\d+)\s*", value or "")
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


def dotted(version: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in version)


def marker_count(tag: str) -> int | None:
    """How many times the hub#1595 marker appears in that file at `tag`. `None` = cannot look."""
    path, marker = KERNEL_MARKER
    try:
        blob = subprocess.run(
            ["git", "-C", str(HUB_CHECKOUT), "show", f"{tag}:{path}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return blob.stdout.count(marker) if blob.returncode == 0 else None


def main() -> int:
    print("· the manifest declares which hub this module needs (whatsapp_inbox#62)")

    declared = (MANIFEST.get("compatibility") or {}).get("min_erplora_version")
    if not declared:
        failures.append(
            "`module.json` declares no `compatibility.min_erplora_version`, so a hub older than "
            f"{dotted(KERNEL_FLOOR)} installs this module and the appointment automation fails "
            "mute: the availability read waits for an approval nobody can grant. Declare "
            f'`"compatibility": {{ "min_erplora_version": "{dotted(KERNEL_FLOOR)}" }}` — the hub '
            "refuses the install with `core_version_too_old` (ERPlora/hub#521)"
        )
        return report()

    floor = triple(declared)
    if floor is None:
        failures.append(
            f"`compatibility.min_erplora_version` is `{declared}`, which is not an `x.y.z` the hub "
            "can compare against: it refuses the install as `manifest_core_floor_unreadable`, so "
            "the module stops installing ANYWHERE instead of only on old hubs"
        )
        return report()
    print(f"  ok: declares `{declared}`, a version the runtime can compare")

    if floor < KERNEL_FLOOR:
        failures.append(
            f"the declared floor `{declared}` is below {dotted(KERNEL_FLOOR)}, the first release "
            "carrying ERPlora/hub#1595. Between the two, the automation installs and the "
            "appointment is never proposed — which is the whole failure this floor prevents"
        )
    else:
        print(
            f"  ok: `{declared}` >= {dotted(KERNEL_FLOOR)}, the release that carries hub#1595"
        )

    # The floor stops being a claim about the kernel the moment nothing here needs the kernel.
    templates = sorted(p.name for p in (MODULE_DIR / "flows").glob("*.flow.json"))
    if not templates:
        failures.append(
            "this module ships no `flows/*.flow.json` any more, so the reason for the core floor "
            "is gone: re-derive it (or drop it) instead of leaving a number nobody can justify"
        )
    else:
        print(
            f"  ok: {len(templates)} flow template(s) still ride on that kernel behaviour"
        )

    # 4 · Re-measure instead of trusting the table in the docstring.
    path, marker = KERNEL_MARKER
    at_floor, measured_tag = marker_count(f"v{declared}"), f"v{declared}"
    if at_floor is None and floor > KERNEL_FLOOR:
        # A floor above the newest published tag is the CORRECT way to ship something the fleet
        # cannot run yet, so there is nothing to read at `v{declared}`. Falling back to the kernel
        # floor keeps the control alive instead of turning that legitimate case into a blind skip.
        at_floor, measured_tag = (
            marker_count(f"v{dotted(KERNEL_FLOOR)}"),
            f"v{dotted(KERNEL_FLOOR)}",
        )
    before = marker_count(KERNEL_FLOOR_MINUS_ONE)
    if at_floor is None or before is None:
        print(
            f"  ⚠ SKIPPED the re-measure: cannot read `{path}` at {measured_tag}/"
            f"{KERNEL_FLOOR_MINUS_ONE} from {HUB_CHECKOUT} (no hub checkout, or its tags are not "
            "fetched). The three checks above still ran."
        )
    elif before:
        failures.append(
            f"`{marker}` already appears in `{path}` at {KERNEL_FLOOR_MINUS_ONE}, so this control "
            "cannot tell the releases apart: the measurement behind the floor is stale, re-derive "
            "which tag first carries hub#1595"
        )
    elif not at_floor:
        failures.append(
            f"`{marker}` is NOT in `{path}` at {measured_tag}: the declared floor points at a release "
            "that does not carry hub#1595, so it promises something the hub does not do"
        )
    else:
        print(
            f"  ok: re-measured — `{marker}` appears {at_floor}x at {measured_tag} and 0x at "
            f"{KERNEL_FLOOR_MINUS_ONE}"
        )

    return report()


def report() -> int:
    if failures:
        print(f"\nFAIL ({len(failures)}):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("\nOK: an old hub is told to update instead of installing a mute automation")
    return 0


if __name__ == "__main__":
    sys.exit(main())

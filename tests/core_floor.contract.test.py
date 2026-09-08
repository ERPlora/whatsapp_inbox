#!/usr/bin/env python3
"""This module says WHICH hub it needs, so an old one refuses it instead of failing mute (#62).

WHY THIS FILE EXISTS. The automations this module ships (`flows/`) lean on kernel behaviour, and
every way of not having it is SILENT. On a hub without hub#1595 the first availability read of
`propose_appointment` turns into a row of `_flow_approvals` and the turn ends, so the owner gets a
card asking them to approve «check availability» — which is not a decision anybody can take — and
the appointment is never proposed. Nothing throws, nothing warns at install time, and the business
finds out when a customer is left without an appointment.

The manifest is the only place that can say no in time. `compatibility.min_erplora_version` is read
by the runtime (`Manifest::load` → `require_core_version`, hub#521): a core below the declared floor
refuses the install with `core_version_too_old` — "the module `x` needs a newer version of your
terminal … update the hub and install it again" — instead of half-landing. Until #62 this module
declared nothing, so every hub took it, and `flows/README.md` carried the requirement as prose:
documentation is not a guard.

🔴 **AND THE JSON SCHEMA IS NOT THE GATE** (whatsapp_inbox#101, measured 2026-09-07). It is tempting
to protect a template by probing the `flow.schema.json` the hub serves, the way flows#75 protects a
SCREEN. Measured against the fleet's own release, that probe answers WRONG: `flow.schema.json` at
`v1.1.15` validates a document carrying `interactive` and `output` with **zero** errors, because the
step object has no `additionalProperties: false`. What refuses it is the Rust parser one layer in —
`def.rs` walks an ALLOWLIST per step kind and returns `flow.invalid_definition` on the first key it
does not know. So the document does not degrade, it does not partly work, and the schema cannot see
it coming: the whole automation is refused at save time. A version floor is the only control that
runs BEFORE the module lands.

WHAT THIS PINS:

  1. the manifest declares a core floor AT ALL (deleting it brings the mute failure back);
  2. the floor is a version the hub can compare against — an unreadable one is refused too
     (`ManifestCoreFloorUnreadable`), so a typo would brick the install rather than loosen it;
  3. it is not below what the SHIPPED TEMPLATES actually ask the kernel for. Derived from the
     documents AND the grant sidecars in `flows/` — not from a constant somebody remembers to
     bump: a template that starts using a newer kernel feature, or a permission that starts
     fixing a value only a newer kernel applies, raises the floor by existing, which is the
     whole point;
  4. and every requirement is RE-MEASURED against the neighbouring hub checkout instead of
     trusted: the marker has to be PRESENT at the declared release AND ABSENT at the release before
     it. A control that cannot tell the two apart would pass no matter what the floor said.

THE KERNEL FLOORS, MEASURED (2026-09-08, `git show <ref>:<path> | grep -c <marker>`):

  | ref            | `answers_only`  | `AiOutputKind` | `interactive` | `fn can_pin`   | `PIN_ROOTS`    |
  |                | agent_runner.rs | def.rs         | def.rs        | flows/grants.rs| flows/grants.rs|
  |----------------|-----------------|----------------|---------------|----------------|----------------|
  | v1.1.14        | absent          | absent         | absent        | absent         | absent         |
  | v1.1.15        | present (x5)    | absent         | absent        | absent         | absent         |
  | v1.1.16        | present (x5)    | present (x17)  | present (x33) | absent         | absent         |
  | origin/develop | present (x5)    | present (x17)  | present (x33) | present (x1)   | present (x3)   |

So `v1.1.15` is the first release carrying hub#1595, `v1.1.16` the first carrying
hub#1633/hub#1639, and NO release yet carries hub#1662 — `git tag --contains 17fe65ce` is empty.
`1.1.17` is therefore a floor pointing at a release that does not exist yet, which is the CORRECT
way to ship something the fleet cannot run: the hub refuses the install with `core_version_too_old`
instead of taking a template that explodes at save time. The positive half of the re-measure falls
back to `origin/develop` while that tag is missing, so the marker still has to be real somewhere
rather than merely asserted here.

🔴 AND THE FLOOR IS NOT ONLY IN THE DOCUMENTS (whatsapp_inbox#119). Since hub#1654 the
`<family>.grants.json` travels to the hub as well, and what a permission DECLARES there is refused
by an older core exactly as hard as an unknown step key — harder, in fact: `PUT …/grants` is
all-or-nothing, so a `payload` an old hub does not accept on a `query` does not degrade to the wide
permission, it leaves the recipe with NO permissions. `GRANT_FEATURES` derives from the sidecars for
that reason; deriving from the documents alone would have let this pin ship under a floor that
predates pinning.

Usage: tests/core_floor.contract.test.py   (exit 0 = green). No Postgres, no Docker.
"""

import json
import pathlib
import re
import subprocess
import sys
from typing import NamedTuple

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())
# Sibling checkout of ERPlora/hub in the monorepo (`modules-workspace/modules/<id>` → root).
HUB_CHECKOUT = MODULE_DIR.parent.parent.parent / "hub"


class KernelNeed(NamedTuple):
    """One kernel behaviour a template leans on, with the evidence for its release number."""

    issue: str
    floor: tuple[int, int, int]
    path: str
    marker: str
    last_without: str
    why: str


NEED_ANSWERS_ONLY = KernelNeed(
    issue="hub#1595",
    floor=(1, 1, 15),
    path="crates/server/src/agent_runner.rs",
    marker="answers_only",
    last_without="v1.1.14",
    why="a command that only ANSWERS runs inside the turn whatever the policy says. Without it "
    "the availability read parks as an approval nobody can grant and the appointment is never "
    "proposed",
)
NEED_DECLARED_OUTPUT = KernelNeed(
    issue="hub#1639",
    floor=(1, 1, 16),
    path="crates/runtime/src/flows/def.rs",
    marker="AiOutputKind",
    last_without="v1.1.15",
    why="an `ai` step DECLARES what its turn leaves behind (`output`), so a later step can map "
    "`steps.<id>.<field>`. Below it, `output` is an unknown key and the parser refuses the WHOLE "
    "document with `flow.invalid_definition`",
)
NEED_INTERACTIVE = KernelNeed(
    issue="hub#1633",
    floor=(1, 1, 16),
    path="crates/runtime/src/flows/def.rs",
    marker="interactive",
    last_without="v1.1.15",
    why="a `notify` step carries Meta's own `interactive` object, which is what the customer TAPS. "
    "Below it, `interactive` is an unknown key and the parser refuses the WHOLE document with "
    "`flow.invalid_definition`",
)

NEED_PINNED_READ = KernelNeed(
    issue="hub#1662",
    floor=(1, 1, 17),
    path="crates/runtime/src/flows/grants.rs",
    marker="fn can_pin",
    last_without="v1.1.16",
    why="a grant may fix payload values on a `query`, so «may read a diary» becomes «may read "
    "THIS customer's diary». Below it `check_grants` refuses a `payload` on anything but a "
    "`command` — and `PUT …/grants` is ALL-OR-NOTHING, so the recipe does not install with the "
    "wide permission, it installs with NO permission at all and dies on its first step",
)
NEED_PIN_REFERENCE = KernelNeed(
    issue="hub#1662",
    floor=(1, 1, 17),
    path="crates/runtime/src/flows/grants.rs",
    marker="PIN_ROOTS",
    last_without="v1.1.16",
    why="a fixed value may NAME a place in the run (`steps.<id>.<field>`) instead of being a "
    "literal, which is the only shape an identity can take — who the run is about is not known "
    "until it resolves her. Measured separately from `can_pin` on purpose: a hub that stored the "
    "pin without resolving it would compare the literal string `steps.resolve_customer.id` "
    "against a real id and deny every single read",
)

# What a shipped document has to contain for each need to be REAL, so the floor is derived from the
# templates rather than from a number somebody has to remember to raise (whatsapp_inbox#101).
FEATURES = (
    (NEED_INTERACTIVE, "interactive", lambda step: bool(step.get("interactive"))),
    (NEED_DECLARED_OUTPUT, "output", lambda step: bool(step.get("output"))),
)
# …and the same, one file over. A kernel need does not only come from the DOCUMENT: since hub#1654
# the `<family>.grants.json` travels to the hub too, and what it declares there is refused by an
# older core exactly as hard (whatsapp_inbox#119). Reading only the documents would have let a pin
# ship under a floor that predates pinning.
GRANT_FEATURES = (
    (
        NEED_PINNED_READ,
        "a `query` grant fixes payload values",
        lambda grant: grant.get("kind") == "query" and bool(grant.get("payload")),
    ),
    (
        NEED_PIN_REFERENCE,
        "a pin NAMES a place in the run instead of fixing a literal",
        lambda grant: any(
            isinstance(v, str) and "." in v and v.split(".")[0] in PIN_ROOTS
            for v in (grant.get("payload") or {}).values()
        ),
    ),
)
# The roots `check_pin_value` accepts, and nothing else: `secret.…` is refused on purpose (it would
# turn the gate into an oracle) and `event.…` is not in the run scope.
PIN_ROOTS = ("input", "steps")
# …and this one is not a step key: it is why the module declared a floor in the first place, and
# every template still rides on it, so it is asked of the whole family.
ALWAYS = (NEED_ANSWERS_ONLY,)

failures: list[str] = []


def triple(value: str) -> tuple[int, int, int] | None:
    """`x.y.z` as the runtime parses it (`manifest::version_triple`), or `None`."""
    match = re.fullmatch(r"\s*(\d+)\.(\d+)\.(\d+)\s*", value or "")
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


def dotted(version: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in version)


def marker_count(ref: str, path: str, marker: str) -> int | None:
    """How many times `marker` appears in `path` at `ref`. `None` = cannot look."""
    try:
        blob = subprocess.run(
            ["git", "-C", str(HUB_CHECKOUT), "show", f"{ref}:{path}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return blob.stdout.count(marker) if blob.returncode == 0 else None


def needs_of_templates() -> list[tuple[KernelNeed, str]]:
    """Every kernel need the shipped documents actually demand, with who demands it."""
    demanded: list[tuple[KernelNeed, str]] = []
    templates = sorted((MODULE_DIR / "flows").glob("*.flow.json"))
    for template in templates:
        doc = json.loads(template.read_text(encoding="utf-8"))
        for need, label, present in FEATURES:
            hits = [s.get("id") for s in doc.get("steps", []) if present(s)]
            if hits:
                demanded.append((need, f"{template.name} step `{hits[0]}` uses `{label}`"))
    for sidecar in sorted((MODULE_DIR / "flows").glob("*.grants.json")):
        body = json.loads(sidecar.read_text(encoding="utf-8"))
        grants = body.get("grants", []) if isinstance(body, dict) else body
        for need, label, present in GRANT_FEATURES:
            hits = [g for g in grants if isinstance(g, dict) and present(g)]
            if hits:
                demanded.append(
                    (need, f"{sidecar.name} `{hits[0].get('kind')} {hits[0].get('value')}` — {label}")
                )
    if templates:
        for need in ALWAYS:
            demanded.append((need, f"all {len(templates)} template(s) ride on it"))
    return demanded


def main() -> int:
    print("· the manifest declares which hub this module needs (whatsapp_inbox#62)")

    templates = sorted(p.name for p in (MODULE_DIR / "flows").glob("*.flow.json"))
    if not templates:
        failures.append(
            "this module ships no `flows/*.flow.json` any more, so the reason for the core floor "
            "is gone: re-derive it (or drop it) instead of leaving a number nobody can justify"
        )
        return report()

    declared = (MANIFEST.get("compatibility") or {}).get("min_erplora_version")
    if not declared:
        failures.append(
            "`module.json` declares no `compatibility.min_erplora_version`, so an old hub installs "
            "this module and the automation fails mute — the availability read waits for an "
            "approval nobody can grant, or the whole document is refused at save time. Declare "
            '`"compatibility": { "min_erplora_version": "x.y.z" }` — the hub then refuses the '
            "install with `core_version_too_old` (ERPlora/hub#521)"
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

    demanded = needs_of_templates()
    print(f"  ok: {len(templates)} template(s) demand {len(demanded)} kernel behaviour(s)")

    # 3 · The floor covers everything the SHIPPED documents ask for.
    for need, who in demanded:
        if floor < need.floor:
            failures.append(
                f"{who}, which needs {need.issue} — first carried by {dotted(need.floor)} — and "
                f"the manifest declares `{declared}`. {need.why}. On a hub between the two the "
                f"module INSTALLS and the automation is dead, with nothing said anywhere: raise "
                f"`compatibility.min_erplora_version` to {dotted(need.floor)} so the install is "
                f"refused with `core_version_too_old` instead"
            )
    if not failures:
        print(
            f"  ok: `{declared}` >= every floor the templates demand "
            f"({', '.join(sorted({dotted(n.floor) for n, _ in demanded}))})"
        )

    # 4 · Re-measure each need instead of trusting the table in the docstring: PRESENT at its
    #     release, ABSENT at the one before it.
    for need in sorted({n for n, _ in demanded}):
        at_floor, measured = marker_count(f"v{dotted(need.floor)}", need.path, need.marker), (
            f"v{dotted(need.floor)}"
        )
        if at_floor is None:
            # A floor above the newest published tag is the CORRECT way to ship something the fleet
            # cannot run yet, so there is nothing to read there. Reading `origin/develop` instead
            # keeps the positive half alive — the capability still has to exist somewhere — rather
            # than turning that legitimate case into a blind skip.
            at_floor, measured = (
                marker_count("origin/develop", need.path, need.marker),
                "origin/develop",
            )
        before = marker_count(need.last_without, need.path, need.marker)
        if at_floor is None or before is None:
            print(
                f"  ⚠ SKIPPED the re-measure of {need.issue}: cannot read `{need.path}` at "
                f"{measured}/{need.last_without} from {HUB_CHECKOUT} (no hub checkout, or its tags "
                "are not fetched). The checks above still ran."
            )
        elif before:
            failures.append(
                f"`{need.marker}` already appears in `{need.path}` at {need.last_without}, so this "
                f"control cannot tell the releases apart: the measurement behind the "
                f"{dotted(need.floor)} floor of {need.issue} is stale, re-derive which release "
                f"first carries it"
            )
        elif not at_floor:
            failures.append(
                f"`{need.marker}` is NOT in `{need.path}` at {measured}: the floor "
                f"{dotted(need.floor)} points at a release that does not carry {need.issue}, so it "
                f"promises something the hub does not do"
            )
        else:
            print(
                f"  ok: re-measured {need.issue} — `{need.marker}` appears {at_floor}x at "
                f"{measured} and 0x at {need.last_without}"
            )

    return report()


def report() -> int:
    if failures:
        print(f"\nFAIL ({len(failures)}):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("\nOK: an old hub is told to update instead of installing an automation it cannot run")
    return 0


if __name__ == "__main__":
    sys.exit(main())

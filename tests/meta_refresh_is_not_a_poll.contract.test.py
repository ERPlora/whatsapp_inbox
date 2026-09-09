#!/usr/bin/env python3
"""Meta's verdicts are read when the tab OPENS, never on a timer (whatsapp_inbox#134).

The templates tab puts Meta's verdict on its rows by reading the runtime's door
(`erplora.forModule('whatsapp_inbox').whatsappTemplates.list()`). That read is not cheap and it is
not ours: the SaaS refreshes against Meta on **every** call and the path carries no throttle of its
own (hub#1610, and the warning the reviewer of ERPlora/saas#1905 left). A `setInterval` next to that
call is one request to Meta per open tab per tick, across every hub — the kind of thing that reads
as an innocent «keep it fresh» in a diff and arrives as a rate limit for every business at once.

The Web Component test next door proves the read happens and happens ONCE per mount. It cannot
prove the absence of a timer someone adds later: `vitest` would have to sit and wait for a tick it
does not know the length of. This battery is the half that can — it reads the source.

Two things are checked, and the second is what keeps the first honest:

1. **No scheduler in the templates screen.** `setInterval`, `setTimeout` and `requestIdleCallback`
   are all out: a `setTimeout` that re-arms itself is an interval with extra steps.
2. **The screen still calls the door**, so this file cannot pass by describing a screen that no
   longer syncs at all. A guard that stays green after the feature is deleted is not a guard.

Usage: tests/meta_refresh_is_not_a_poll.contract.test.py   (exit 0 = green). No Postgres, no Docker.
"""

import pathlib
import re
import sys

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
SCREEN = MODULE_DIR / "ui/components/erp-whatsapp-inbox-templates/erp-whatsapp-inbox-templates.ts"

#: Every way a browser can be asked to come back later. `requestAnimationFrame` is deliberately out
#: of the list: it is a paint hook, it does not survive a backgrounded tab, and nobody polls with it.
SCHEDULERS = ("setInterval", "setTimeout", "requestIdleCallback")

#: What proves the screen still reads the door at all.
DOOR_READ = ".whatsappTemplates.list("


def strip_comments(source: str) -> str:
    """The CODE of a TypeScript file, with `//` lines and `/* … */` blocks taken out.

    Same helper and same caveat as `meta_door_capability.contract.test.py`: it errs towards reading
    LESS. For a gate that is the safe direction — it can lose a caller and fail loud, never invent
    one — and here it is what lets the doc-comment above `refreshMetaVerdicts` say the word
    «setInterval» out loud while explaining why there is none.
    """
    without_blocks = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"^\s*//.*$", "", without_blocks, flags=re.MULTILINE)


def schedulers_in(code: str) -> list[str]:
    """The schedulers this code CALLS, matched as calls (`setInterval(`) and not as bare names."""
    return [name for name in SCHEDULERS if f"{name}(" in code]


# The two predicates, proved against SYNTHETIC sources in BOTH directions. Without this the file
# would be asserting «today's screen looks like today's screen», which is true of any screen.
PREDICATE_CASES = (
    (
        "a screen that polls Meta",
        "connectedCallback() { setInterval(() => this.refreshMetaVerdicts(), 60000); }",
        ["setInterval"],
        False,
    ),
    (
        "a screen that re-arms a timeout, which is an interval with extra steps",
        "private tick() { setTimeout(() => this.tick(), 60000); }",
        ["setTimeout"],
        False,
    ),
    (
        "a screen that waits for an idle moment to ask again",
        "requestIdleCallback(() => this.refreshMetaVerdicts());",
        ["requestIdleCallback"],
        False,
    ),
    (
        "the screen this module ships: reads the door once, on connect",
        "async connectedCallback() {\n"
        "  const a = await erplora().forModule('whatsapp_inbox').whatsappTemplates.list();\n"
        "}",
        [],
        True,
    ),
    (
        "a screen that only DESCRIBES the door without reading it",
        "interface Door { list(): Promise<unknown>; }",
        [],
        False,
    ),
)


def main() -> int:
    failures: list[str] = []

    for label, source, expected_schedulers, expected_reads_door in PREDICATE_CASES:
        code = strip_comments(source)
        found = schedulers_in(code)
        if found != expected_schedulers:
            failures.append(
                f"predicate: {label} → schedulers {found}, expected {expected_schedulers}"
            )
        reads = DOOR_READ in code
        if reads != expected_reads_door:
            failures.append(
                f"predicate: {label} → reads the door {reads}, expected {expected_reads_door}"
            )

    if not SCREEN.exists():
        failures.append(f"{SCREEN.relative_to(MODULE_DIR)} is gone: this gate has nothing to read")
        code = ""
    else:
        code = strip_comments(SCREEN.read_text())

    found = schedulers_in(code)
    if found:
        failures.append(
            f"{SCREEN.relative_to(MODULE_DIR)} schedules {', '.join(found)}. Meta's verdicts are "
            "read when the tab OPENS: that door refreshes against Meta on every call and carries "
            "no throttle, so a timer here is one call to Meta per open tab per tick."
        )

    if code and DOOR_READ not in code:
        failures.append(
            f"{SCREEN.relative_to(MODULE_DIR)} no longer calls `{DOOR_READ}`. Either the tab stopped "
            "putting Meta's verdicts up to date (whatsapp_inbox#134 is back) or this gate has to be "
            "pointed at whatever reads them now — it must not stay green by watching nothing."
        )

    for line in failures:
        print(f"FAIL: {line}")
    if failures:
        return 1
    print(f"OK: {SCREEN.relative_to(MODULE_DIR)} reads Meta on open and schedules nothing")
    return 0


if __name__ == "__main__":
    sys.exit(main())

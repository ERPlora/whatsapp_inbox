#!/usr/bin/env python3
"""The door to Meta only opens for a module that DECLARED the channel (whatsapp_inbox#87).

The templates screen registers what the owner wrote with Meta through the runtime's door
(`erplora.forModule('whatsapp_inbox').whatsappTemplates.*`, hub#1682). That door is gated in TWO
halves, and the second one is the one nobody remembers:

  1. the `notify` capability has to be GRANTED to this module, and
  2. the module has to have DECLARED the channel it wants to use —
     `crates/runtime/src/host_notify.rs::assert_channel_declared` reads
     `capabilities.notify.channels` off the installed manifest and refuses anything not in it.

The second half was added by the reviewer of ERPlora/hub#1687 for a real hole: a module holding
`notify` for EMAIL could delete another module's approved WhatsApp templates. The consequence for
this module is blunt — with `notify` but no `whatsapp` channel, all three routes answer
`403 capability_denied` and every registration fails, while the manifest still installs fine and
every other battery in this repo stays green. Measured on 2026-09-09: emptying `channels` left the
23 batteries of `erplora test .` green, which is exactly the kind of silence this repo does not
keep (root CLAUDE.md, «cero regresiones»).

So this gate ties the two together and answers both from the code, never from memory:

1. **If a screen CALLS the door, the manifest declares `notify` with the `whatsapp` channel.**
2. **Every channel it declares is one the runtime can parse.** `Channel::parse` matches the exact
   lowercase word (`email` / `sms` / `whatsapp`) and nothing else, so `"WhatsApp"` is not a
   near-miss — it is a channel the hub has never heard of, failing the same silent 403.

Usage: tests/meta_door_capability.contract.test.py   (exit 0 = green). No Postgres, no Docker.
"""

import json
import pathlib
import re
import sys

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())

#: The channels `crates/runtime/src/host_notify.rs::Channel::parse` answers to, verbatim. Anything
#: else parses to `None` and can never satisfy `assert_channel_declared`.
RUNTIME_CHANNELS = ("email", "sms", "whatsapp")

#: The methods of the SDK surface that go through the gated routes (hub#1682).
DOOR_METHODS = ("register", "list", "remove")


def strip_comments(source: str) -> str:
    """The CODE of a TypeScript file, with `//` lines and `/* … */` blocks taken out.

    Same helper, same caveat as `core_floor.contract.test.py`: it errs towards reading LESS, which
    for a gate is the safe direction — it can lose a caller and fail loud, never invent one.
    """
    without_blocks = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"^\s*//.*$", "", without_blocks, flags=re.MULTILINE)


def calls_the_door(code: str) -> bool:
    """Whether this source CALLS the door, as opposed to merely describing it.

    Matched as a call — `.whatsappTemplates.<method>(` — and never as the bare name, for the same
    reason `core_floor` does it: the screen also DECLARES the door's shape to type it
    (`forModule(id): { whatsappTemplates: WhatsappTemplatesDoor }`), and a name-only match would go
    on demanding the capability after the call itself was deleted. A guard that cannot stop
    demanding is a constant, and a constant catches nothing.
    """
    return any(f".whatsappTemplates.{method}(" in code for method in DOOR_METHODS)


# The predicate above, proved against SYNTHETIC sources in BOTH directions. The UI is the one input
# this battery does not get to choose, so a predicate that quietly stopped discriminating would keep
# reading «the door is called» off today's screen and go on reading it after the call was gone.
PREDICATE_CASES = (
    (
        "a screen that registers the template with Meta",
        "const v = await erplora().forModule(MODULE_ID).whatsappTemplates.register(reviewed);",
        True,
    ),
    (
        "a screen that lists what Meta holds",
        "const { templates } = await door.whatsappTemplates.list();",
        True,
    ),
    (
        # The load-bearing negative: this exact declaration ships next to the call in
        # `erp-whatsapp-inbox-templates.ts`, and it is CODE — `strip_comments` does not touch it.
        "a screen that only DECLARES the door's shape to type it, and never calls it",
        "forModule(id: string): { whatsappTemplates: WhatsappTemplatesDoor };",
        False,
    ),
    (
        "a screen that only NAMES the door in a comment",
        "// the owner's templates live behind whatsappTemplates.register\nconst x = 1;",
        False,
    ),
)


def ui_sources():
    """The module's own screens: `ui/**/*.ts`, minus the tests, which are not what ships."""
    return sorted(
        path
        for path in (MODULE_DIR / "ui").rglob("*.ts")
        if not path.name.endswith(".test.ts")
    )


def declared_channels():
    """`capabilities.notify.channels`, plus the legacy top-level `notify` the runtime still reads."""
    blocks = (
        (MANIFEST.get("capabilities") or {}).get("notify") or {},
        MANIFEST.get("notify") or {},
    )
    return [
        channel
        for block in blocks
        for channel in (block.get("channels") or [])
    ]


def check_the_check_reaches_the_screen():
    """A gate that reads nothing passes everything. The screens have to be there to be read."""
    sources = ui_sources()
    if not sources:
        return [
            "this gate read NO `ui/**/*.ts` at all, so it cannot have checked anything. Either the "
            "screens moved or `ui_sources()` stopped finding them"
        ]
    return []


def check_the_predicate_discriminates():
    problems = []
    for label, source, expected in PREDICATE_CASES:
        actual = calls_the_door(strip_comments(source))
        if actual != expected:
            problems.append(
                f"`calls_the_door` says {actual} about {label}, expected {expected}. The predicate "
                f"no longer tells a CALL from a mention, so what it reports about the real screens "
                f"proves nothing"
            )
    return problems


def check_the_channel_is_declared():
    callers = [
        path.relative_to(MODULE_DIR)
        for path in ui_sources()
        if calls_the_door(strip_comments(path.read_text()))
    ]
    if not callers:
        return []

    if "whatsapp" in declared_channels():
        return []

    where = ", ".join(f"`{path}`" for path in callers)
    return [
        f"{where} call(s) the runtime's WhatsApp templates door, but `module.json` does not declare "
        f"`capabilities.notify.channels` containing `whatsapp` (it declares "
        f"{declared_channels() or 'nothing'}). `assert_channel_declared` "
        f"(`hub: crates/runtime/src/host_notify.rs`) refuses every one of those calls with "
        f"`403 capability_denied`, so the owner presses «Guardar» and the template never reaches "
        f"Meta — with the module installed, the screen painted and this suite green"
    ]


def check_every_channel_is_one_the_runtime_KNOWS():
    problems = []
    for channel in declared_channels():
        if channel not in RUNTIME_CHANNELS:
            problems.append(
                f"`module.json` declares the notify channel `{channel}`, which "
                f"`Channel::parse` (`hub: crates/runtime/src/host_notify.rs`) does not answer to — "
                f"it matches {', '.join(f'`{c}`' for c in RUNTIME_CHANNELS)} exactly and is "
                f"case-sensitive. A channel the hub cannot parse is not a narrower permission, it "
                f"is no permission: the route answers `403 capability_denied` just the same"
            )
    return problems


def main():
    problems = []
    problems += check_the_check_reaches_the_screen()
    problems += check_the_predicate_discriminates()
    problems += check_the_channel_is_declared()
    problems += check_every_channel_is_one_the_runtime_KNOWS()

    for problem in problems:
        print(f"FAIL  {problem}")
    if problems:
        print(f"\n{len(problems)} thing(s) between the screen and the door to Meta that do not meet")
        return 1

    print(
        f"OK: the screen calls the door and `module.json` declares it — notify channel(s) "
        f"{declared_channels()}, all of them ones the runtime parses; and the caller predicate "
        f"still tells a call from a mention ({len(PREDICATE_CASES)} cases, both directions)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

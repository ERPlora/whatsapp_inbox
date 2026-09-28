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
  4. nor ABOVE it: a floor higher than anything the shipped files demand is a number nothing
     derives any more, which is what every derivation going blind at once looks like. The table is
     anchored in BOTH directions, so blinding the sidecar reading cannot turn this file green;
  5. and every requirement is RE-MEASURED against the neighbouring hub checkout instead of
     trusted: the marker has to be PRESENT at the declared release AND ABSENT at the release before
     it. A control that cannot tell the two apart would pass no matter what the floor said.

THE KERNEL FLOORS, MEASURED (2026-09-08, `git show <ref>:<path> | grep -c <marker>`):

  | ref            | `answers_only`  | `AiOutputKind` | `interactive` | `ApprovalStep::` | `ON_ERROR_`    | `fn can_pin`   | `PIN_ROOTS`    |
  |                | agent_runner.rs | def.rs         | def.rs        | `on_expire`      | `CONTINUE`     | flows/grants.rs| flows/grants.rs|
  |                |                 |                |               | def.rs           | def.rs         |                |                |
  |----------------|-----------------|----------------|---------------|------------------|----------------|----------------|----------------|
  | v1.1.14        | absent          | absent         | absent        | absent           | absent         | absent         | absent         |
  | v1.1.15        | present (x5)    | absent         | absent        | absent           | absent         | absent         | absent         |
  | v1.1.16        | present (x5)    | present (x17)  | present (x33) | present (x1)     | present (x3)   | absent         | absent         |
  | v1.1.17        | present (x5)    | present (x17)  | present (x33) | present (x1)     | present (x3)   | present (x1)   | present (x3)   |
  | origin/develop | present (x5)    | present (x17)  | present (x33) | present (x1)     | present (x3)   | present (x1)   | present (x3)   |

So `v1.1.15` is the first release carrying hub#1595 and `v1.1.16` the first carrying
hub#1633/hub#1639 and hub#1634/hub#1635; hub#1662 arrived in `v1.1.17`.
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

# 🔴 THE TEMPLATES ARE NOT THE ONLY THING THAT RAISES THE FLOOR (module-toolkit#201).
# `erplora build` makes a self-contained bundle: it inlines the OutfitKit of whoever built it, and
# `dist/outfitkit.json` records which one. That version is a second, independent source of floor.
# On a hub whose shell carries an OLDER OutfitKit the screens render with the shell's `ok-*`, not
# with the ones this module was tested against (ADR-0133) — nothing fails, the screen is just
# different from the one that was signed off, which is the worst shape a defect can take.
#
# The rule and the hub↔OutfitKit table belong to the toolkit (`validate-outfitkit-floor.mjs`), and
# that table is derived from release DATES — the hub pins `^0.1.52` at every tag and resolves the
# real version when the image is built, so there is NO file here, or in the hub, that can be
# re-measured to prove it. That is why this is not a `KernelNeed`: it has no marker.
#
# What this test owns is narrower, and is what keeps the number from going bare: the floor may sit
# above what the templates demand ONLY while the shipped stamp says so, and the (bake → floor) pair
# is written down right here. Rebake against a different OutfitKit and this line stops matching the
# artifact, so the floor has to be derived again instead of being inherited by accident.
OUTFITKIT_STAMP = MODULE_DIR / "dist" / "outfitkit.json"
# 0.1.89 (whatsapp_inbox#225): since module-toolkit#346 `erplora validate` judges the stamp by the
# API the module uses on the shell's `ok-*`, type-checked against the floor hub's OutfitKit; the
# bundle passes at 1.1.22 (ok-lightbox, the reason for the rebake, is painted by the module itself).
OUTFITKIT_BAKE_FLOOR = ("0.1.89", (1, 1, 22))


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

NEED_AI_EXPIRY = KernelNeed(
    issue="hub#1634",
    floor=(1, 1, 16),
    path="crates/runtime/src/flows/def.rs",
    marker="ApprovalStep::on_expire",
    last_without="v1.1.15",
    why="an `ai` step declares what a SILENCE costs the run, so a proposal nobody ever answered "
    "carries on to the step that tells the customer instead of cancelling the run at 72 h. Below "
    "it `on_expire` is an unknown key on that kind and the parser refuses the WHOLE document "
    "with `flow.invalid_definition`. Measured through the doc-link the key's own field carries "
    "(`[`ApprovalStep::on_expire`]`) rather than through `on_expire` itself, which the APPROVAL "
    "step has had since hub#950 and would therefore read «present» at every release",
)
NEED_STEP_ERROR_POLICY = KernelNeed(
    issue="hub#1635",
    floor=(1, 1, 16),
    path="crates/runtime/src/flows/def.rs",
    marker="ON_ERROR_CONTINUE",
    last_without="v1.1.15",
    why="a step declares what a FAILURE costs the run, so an approved booking that breaks — the "
    "slot taken in between, the professional gone — still reaches the step that tells the "
    "customer instead of ending the run as `failed`. Below it `on_error` is an unknown key on "
    "every kind and the parser refuses the WHOLE document with `flow.invalid_definition`",
)

NEED_STEP_GUARD = KernelNeed(
    issue="hub#2066",
    floor=(1, 1, 30),
    path="crates/runtime/src/flows/def.rs",
    marker="run_if",
    last_without="v1.1.29",
    why="a step may run only when it applies, and the run carries on when it does not — which is "
    "how the recipe tells the customer «someone will answer you here» ONLY when the assistant "
    "failed (whatsapp_inbox#122). Below it `run_if` is an unknown key on every kind and the parser "
    "refuses the WHOLE document with `flow.invalid_definition`: the card would offer a recipe that "
    "cannot be switched on",
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
    # `on_expire` is asked of the `ai` kind ALONE and that is the whole measurement: the APPROVAL
    # step has carried the same key since hub#950, so a predicate that took any step would derive
    # this floor from a document that needs nothing newer than v1.1.14.
    (
        NEED_AI_EXPIRY,
        "on_expire",
        lambda step: step.get("kind") == "ai" and "on_expire" in step,
    ),
    (NEED_STEP_ERROR_POLICY, "on_error", lambda step: "on_error" in step),
    (NEED_STEP_GUARD, "run_if", lambda step: "run_if" in step),
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

NEED_TEMPLATE_ACTIVATE = KernelNeed(
    issue="hub#1677",
    floor=(1, 1, 19),
    path="crates/server/src/routes.rs",
    marker="/api/hub/flows/templates/:module/:family/activate",
    last_without="v1.1.18",
    why="the settings screen turns a factory recipe on IN ONE TAP through the kernel, which "
    "builds it and grants it exactly the sidecar's permissions. Below it the SDK has no such "
    "method, so the screen would paint «Activar» on a hub that answers 404 to it — a button that "
    "fails the moment the owner presses it (whatsapp_inbox#123, ADR-0470)",
)

NEED_TEMPLATE_REGISTER = KernelNeed(
    issue="hub#1688",
    floor=(1, 1, 21),
    path="crates/server/src/whatsapp_templates.rs",
    marker="proxy_cloud_get_enveloped",
    last_without="v1.1.20",
    why="the templates screen registers what the owner wrote WITH Meta and puts back the verdict. "
    "The `whatsappTemplates` surface of the SDK landed one release earlier, in v1.1.20, but its "
    "three doors still answered the SaaS's bare body: every call — the successful ones included — "
    "reached the module as `unknown error`, so a hub on v1.1.20 would tell the owner the "
    "registration failed while Meta had taken the template (whatsapp_inbox#87)",
)

# …and a third place a floor can come from, which is neither the document nor the sidecar: the
# SCREEN (whatsapp_inbox#123). The one-tap activation of ADR-0470 is not a flow feature at all —
# `flows/` is byte for byte what it was — it is `ui/` calling an SDK method that only exists from
# v1.1.19. Deriving the floor only from `flows/` would have left the manifest at 1.1.17 while the
# shipped screen needs 1.1.19, which is the exact failure this battery exists to prevent, one layer
# over: the module installs on a v1.1.17 hub and the owner gets a button that 404s.
#
# 🔴 The source is read with its COMMENTS STRIPPED, and that is load-bearing rather than tidy. This
# very module's screen explains `activateTemplate` at length in its header docstring, so a raw
# substring match would derive the 1.1.19 floor from PROSE — and would go on deriving it after
# somebody deleted the call and left the paragraph behind, which is precisely the regression the
# floor guards. The negative half of `UI_PREDICATE_CASES` pins that.
UI_FEATURES = (
    (
        NEED_TEMPLATE_ACTIVATE,
        "the screen turns a recipe on through the kernel's one-tap door",
        lambda code: "activateTemplate" in code or "deactivateTemplate" in code,
    ),
    (
        NEED_TEMPLATE_REGISTER,
        "the screen registers the template with Meta through the runtime's door",
        # Matched as a CALL (`.whatsappTemplates.<method>(`) and never as the bare name: the screen
        # also DECLARES the door's shape to type it, and a name-only match would keep deriving the
        # floor from that declaration after the call itself was deleted — the regression this
        # exists to catch. Any of the three methods demands it: the envelope is what makes the
        # whole surface answerable, not one route of it.
        lambda code: any(
            f".whatsappTemplates.{method}(" in code
            for method in ("register", "list", "remove")
        ),
    ),
)


def strip_comments(source: str) -> str:
    """The CODE of a TypeScript file, with `//` lines and `/* … */` blocks taken out.

    Nothing clever: string literals containing `//` would be trimmed too. That errs towards reading
    LESS, which for this gate is the safe direction — it can only lose a derivation and fail loud,
    never invent one and pass quiet.
    """
    without_blocks = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"^\s*//.*$", "", without_blocks, flags=re.MULTILINE)


# Every predicate above, proved against SYNTHETIC steps in both directions — the step that must
# demand the floor and the step that must NOT. The documents are the one input this battery does
# not get to choose (it reads whatever `flows/` ships that day), so a predicate that silently
# stopped discriminating would keep deriving the right answer from today's files and go on
# deriving it after the regression it exists to catch.
#
# The NEGATIVE half is the load-bearing one, and `on_expire` is why this table exists: the APPROVAL
# step has carried that key since hub#950, so a predicate that took any step would read «v1.1.16
# demanded» off a document that needs nothing newer than v1.1.14 — and would go on reading it after
# somebody deleted the `ai` step's key, which is the whole regression the floor guards
# (whatsapp_inbox#70). Measured: dropping the `kind == "ai"` filter left this battery GREEN before
# this table existed.
PREDICATE_CASES = (
    (
        NEED_INTERACTIVE,
        "a `notify` step that sends rows to tap",
        {"kind": "notify", "interactive": {"type": "list"}},
        True,
    ),
    (NEED_INTERACTIVE, "a step that sends plain words", {"kind": "notify"}, False),
    (
        NEED_DECLARED_OUTPUT,
        "an `ai` step that declares the shape it returns",
        {"kind": "ai", "output": {"slots": {"type": "options"}}},
        True,
    ),
    (
        NEED_DECLARED_OUTPUT,
        "an `ai` step that only writes words",
        {"kind": "ai"},
        False,
    ),
    (
        NEED_AI_EXPIRY,
        "an `ai` step that declares what a SILENCE costs the run",
        {"kind": "ai", "on_expire": "continue"},
        True,
    ),
    (
        NEED_AI_EXPIRY,
        "the APPROVAL step's own `on_expire`, a key of that kind since hub#950",
        {"kind": "approval", "on_expire": "reject"},
        False,
    ),
    (
        NEED_STEP_ERROR_POLICY,
        "an `ai` step that declares what a BROKEN WRITE costs the run",
        {"kind": "ai", "on_error": "continue"},
        True,
    ),
    (
        NEED_STEP_ERROR_POLICY,
        "a step that says nothing about failure",
        {"kind": "ai"},
        False,
    ),
    (
        NEED_STEP_GUARD,
        "the apology that runs only when the assistant failed",
        {"kind": "notify", "run_if": {"steps.book.status": {"eq": "failed"}}},
        True,
    ),
    (
        NEED_STEP_GUARD,
        "a `condition` that reads the same status in its `when`, as the kernel always allowed",
        {"kind": "condition", "when": {"steps.book.status": {"neq": "failed"}}},
        False,
    ),
)

# The same, for the screen — synthetic SOURCE this time, and the negative half is why the table is
# here at all. Case 2 is the one that would have caught the mistake: a screen that only TALKS about
# the one-tap door in a comment demands nothing of the hub, and a predicate reading the raw file
# would say it does — this module's own screen explains the door at length in its header. Case 3 is
# the world before ADR-0470, the screen that sent the owner to the gallery to switch it on herself,
# which is exactly the state this floor must NOT be derived from.
UI_PREDICATE_CASES = (
    (
        NEED_TEMPLATE_ACTIVATE,
        "a screen that calls the kernel's one-tap door",
        "const flow = await erplora().forModule(MODULE_ID).flows.activateTemplate(family);",
        True,
    ),
    (
        NEED_TEMPLATE_ACTIVATE,
        "a screen that only MENTIONS the door in a comment it never calls",
        "// Since hub#1677 the kernel exposes activateTemplate for this.\n"
        "const go = () => window.history.pushState({}, '', AUTOMATIONS_PATH);",
        False,
    ),
    (
        NEED_TEMPLATE_REGISTER,
        "a screen that registers the template with Meta",
        "const v = await erplora().forModule(MODULE_ID).whatsappTemplates.register(reviewed);",
        True,
    ),
    (
        NEED_TEMPLATE_REGISTER,
        "a screen that only DECLARES the door's shape to type it, and never calls it",
        # The load-bearing negative. `erp-whatsapp-inbox-templates.ts` carries exactly this
        # declaration next to the call, and it is CODE — `strip_comments` does not touch it. A
        # predicate keyed on the bare name would read the floor off this and go on reading it
        # after the call was deleted, which is the same shape of blindness `on_expire` had.
        "interface WhatsappTemplatesDoor {\n"
        "  whatsappTemplates: { register(t: Record<string, unknown>): Promise<unknown> };\n"
        "}",
        False,
    ),
    (
        NEED_TEMPLATE_ACTIVATE,
        "the screen as it was before ADR-0470, linking out to the gallery",
        "const open = () => window.history.pushState({}, '', galleryPath(use));",
        False,
    ),
)

failures: list[str] = []
# Raised by `predicate_self_check()`, and `report()` refuses to print a green without it. Deleting
# the ONE line that calls the self-check is otherwise a silent pass: the cases still hold, and
# nothing says the derivations were never put in front of them. It is the same hole `applied()`
# closes for the document rules one battery over (whatsapp_inbox#69, mutant N5).
predicates_proved = False


def triple(value: str) -> tuple[int, int, int] | None:
    """`x.y.z` as the runtime parses it (`manifest::version_triple`), or `None`."""
    match = re.fullmatch(r"\s*(\d+)\.(\d+)\.(\d+)\s*", value or "")
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


def dotted(version: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in version)


def newest_tag_below(floor: tuple[int, int, int]) -> str | None:
    """The newest hub release tag strictly below `floor`, as the local checkout knows them.

    `None` = cannot look (no hub checkout). A tag the checkout has not fetched cannot make this
    read WRONG, only older: a tag it does know that sits between a need's `last_without` and its
    `floor` really was published, so the need skipped a release it never measured.
    """
    try:
        tags = subprocess.run(
            ["git", "-C", str(HUB_CHECKOUT), "tag", "--list", "v*"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if tags.returncode != 0:
        return None
    known = [(tag, triple(tag[1:])) for tag in tags.stdout.split()]
    below = [
        (tag, version)
        for tag, version in known
        if version is not None and version < floor
    ]
    return max(below, key=lambda pair: pair[1])[0] if below else None


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
                demanded.append(
                    (need, f"{template.name} step `{hits[0]}` uses `{label}`")
                )
    for sidecar in sorted((MODULE_DIR / "flows").glob("*.grants.json")):
        body = json.loads(sidecar.read_text(encoding="utf-8"))
        grants = body.get("grants", []) if isinstance(body, dict) else body
        for need, label, present in GRANT_FEATURES:
            hits = [g for g in grants if isinstance(g, dict) and present(g)]
            if hits:
                demanded.append(
                    (
                        need,
                        f"{sidecar.name} `{hits[0].get('kind')} {hits[0].get('value')}` — {label}",
                    )
                )
    if templates:
        for need in ALWAYS:
            demanded.append((need, f"all {len(templates)} template(s) ride on it"))
    demanded.extend(needs_of_ui())
    return demanded


def needs_of_ui() -> list[tuple[KernelNeed, str]]:
    """Every kernel need the SHIPPED SCREENS demand, with the file that demands it.

    Tests are excluded on purpose: a `.test.ts` never travels to a hub, so a mock of a method the
    real screen does not call would raise the floor of every business running this module for a
    capability nothing shipped uses.
    """
    demanded: list[tuple[KernelNeed, str]] = []
    sources = sorted(
        path
        for path in (MODULE_DIR / "ui").rglob("*.ts")
        if not path.name.endswith(".test.ts")
    )
    for path in sources:
        code = strip_comments(path.read_text(encoding="utf-8"))
        for need, label, present in UI_FEATURES:
            if present(code):
                demanded.append(
                    (need, f"ui/{path.relative_to(MODULE_DIR / 'ui')} — {label}")
                )
    return demanded


def predicate_self_check() -> None:
    """Prove each `FEATURES` predicate discriminates, instead of trusting today's documents.

    Two halves, and the second is the one that keeps the first honest:

    * every case in `PREDICATE_CASES` gets the verdict it claims;
    * and every predicate in `FEATURES` is named by at least one case in EACH direction. Without
      that, deleting the two rows of a predicate is a silent green — the table shrinks, nothing
      says a predicate went unproved, and the derivation is back to being justified by nothing
      (`table-driven-guards-need-anchoring-in-both-directions`).
    """
    global predicates_proved
    predicates_proved = True

    predicates: dict[KernelNeed, list] = {}
    for need, _label, present in FEATURES:
        predicates.setdefault(need, []).append(present)

    proved: set[tuple[str, bool]] = set()
    for need, what, step, expected in PREDICATE_CASES:
        if need not in predicates:
            failures.append(
                f"`PREDICATE_CASES` proves {need.issue} but no `FEATURES` predicate derives it any "
                f"more, so the case is measuring nothing: drop the case, or restore the predicate"
            )
            continue
        matched = any(present(step) for present in predicates[need])
        if matched != expected:
            owed = "demand" if expected else "NOT demand"
            failures.append(
                f"the {need.issue} predicate reads {what} as "
                f"{'demanding' if matched else 'not demanding'} the {dotted(need.floor)} floor, and "
                f"it must {owed} it. {need.why}"
            )
        proved.add((need.issue, expected))

    for need, _label, _present in FEATURES:
        for expected in (True, False):
            if (need.issue, expected) not in proved:
                half = (
                    "a step that DEMANDS it"
                    if expected
                    else "a step that must NOT demand it"
                )
                failures.append(
                    f"no `PREDICATE_CASES` row proves the {need.issue} predicate against {half}, so "
                    f"nothing here would notice it going blind: the floor it derives would keep "
                    f"coming out right off today's documents and stay right after the regression"
                )
    ui_predicates: dict[KernelNeed, list] = {}
    for need, _label, present in UI_FEATURES:
        ui_predicates.setdefault(need, []).append(present)

    ui_proved: set[tuple[str, bool]] = set()
    for need, what, source, expected in UI_PREDICATE_CASES:
        if need not in ui_predicates:
            failures.append(
                f"`UI_PREDICATE_CASES` proves {need.issue} but no `UI_FEATURES` predicate derives "
                f"it any more, so the case is measuring nothing: drop the case, or restore the "
                f"predicate"
            )
            continue
        code = strip_comments(source)
        matched = any(present(code) for present in ui_predicates[need])
        if matched != expected:
            owed = "demand" if expected else "NOT demand"
            failures.append(
                f"the {need.issue} screen predicate reads {what} as "
                f"{'demanding' if matched else 'not demanding'} the {dotted(need.floor)} floor, and "
                f"it must {owed} it. {need.why}"
            )
        ui_proved.add((need.issue, expected))

    for need, _label, _present in UI_FEATURES:
        for expected in (True, False):
            if (need.issue, expected) not in ui_proved:
                half = (
                    "a screen that DEMANDS it"
                    if expected
                    else "a screen that must NOT demand it"
                )
                failures.append(
                    f"no `UI_PREDICATE_CASES` row proves the {need.issue} screen predicate against "
                    f"{half}, so nothing here would notice it going blind: the floor it derives "
                    f"would keep coming out right off today's sources and stay right after the "
                    f"regression"
                )

    if not failures:
        print(
            f"  ok: {len(FEATURES) + len(UI_FEATURES)} floor derivation(s) proved to "
            f"discriminate, in both directions"
        )


def outfitkit_floor() -> tuple[str | None, tuple[int, int, int] | None]:
    """`(baked OutfitKit, the floor it demands)` read off the SHIPPED stamp.

    `(None, None)` means the module ships no stamp — the state of everything published before
    hub#1024, and «nothing to derive» rather than «nothing to check». A stamp that no longer
    matches `OUTFITKIT_BAKE_FLOOR` returns `(baked, None)`: the floor is unknown until somebody
    re-derives it, and guessing one here is how a wrong number would become permanent.
    """
    try:
        baked = json.loads(OUTFITKIT_STAMP.read_text()).get("outfitkit")
    except (OSError, ValueError):
        baked = None
    if not baked:
        return None, None

    recorded, floor = OUTFITKIT_BAKE_FLOOR
    if baked != recorded:
        failures.append(
            f"`dist/{OUTFITKIT_STAMP.name}` says the bundle now inlines OutfitKit `{baked}`, but "
            f"the floor written here was derived for `{recorded}`. The bundle is published AS IS "
            f"and the shell's `ok-*` win over the inlined copy (ADR-0133), so a hub carrying an "
            f"older OutfitKit renders these screens differently from how they were tested, "
            f"silently. Re-derive the pair — `erplora validate` names the oldest hub that ships "
            f"`{baked}` (module-toolkit#201) — and update `OUTFITKIT_BAKE_FLOOR`"
        )
        return baked, None
    return baked, floor


def main() -> int:
    print("· the manifest declares which hub this module needs (whatsapp_inbox#62)")

    predicate_self_check()

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
    print(
        f"  ok: {len(templates)} template(s) demand {len(demanded)} kernel behaviour(s)"
    )

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
    # …and the bundle is a shipped file too: the OutfitKit it inlines demands its own floor.
    baked, bake_floor = outfitkit_floor()
    if bake_floor is not None and floor < bake_floor:
        failures.append(
            f"the bundle inlines OutfitKit `{baked}` — first carried by {dotted(bake_floor)} — and "
            f"the manifest declares `{declared}`. On a hub between the two the module INSTALLS and "
            f"the shell paints these screens with ITS OutfitKit instead of the one they were "
            f"tested against (ADR-0133), with nothing said anywhere: raise "
            f"`compatibility.min_erplora_version` to {dotted(bake_floor)} so the install is "
            f"refused with `core_version_too_old` instead (module-toolkit#201)"
        )

    if not failures:
        print(
            f"  ok: `{declared}` >= every floor the shipped files demand "
            f"({', '.join(sorted({dotted(n.floor) for n, _ in demanded}))})"
        )
        if bake_floor is not None:
            print(
                f"  ok: `{declared}` >= the {dotted(bake_floor)} the inlined OutfitKit "
                f"`{baked}` demands"
            )

    # 4 · …and NOT ABOVE it either. Step 3 only pushes the floor UP, so every derivation going
    #     blind at once — a predicate that stops matching, a key renamed in the sidecars, a glob
    #     that no longer casts — leaves «>= everything demanded» trivially true and the declared
    #     number justified by nothing. Anchoring the table in BOTH directions is what makes the
    #     derivation load-bearing (`table-driven-guards-need-anchoring-in-both-directions`).
    # The bake counts on this side too, or the check would read «nothing derives 1.1.22» while the
    # stamp right next to it derives exactly that, and the only way to green would be to LOWER the
    # floor below what the bundle needs — turning a guard against blind derivations into a push
    # towards a wrong number.
    highest = max(
        (need.floor for need, _ in demanded),
        default=None if bake_floor is None else bake_floor,
    )
    if highest is not None and bake_floor is not None:
        highest = max(highest, bake_floor)
    if highest is not None and floor > highest:
        failures.append(
            f"the manifest declares `{declared}` but the shipped files only demand up to "
            f"{dotted(highest)}, so nothing derives that number any more: either a derivation went "
            f"blind (a FEATURES/GRANT_FEATURES/UI_FEATURES predicate, a key renamed in `flows/`, a "
            f"call dropped from `ui/`, a glob that stopped matching) or the requirement really is "
            f"gone. Re-derive it — and if the floor "
            f"is meant to stand on something no shipped file can show, it belongs in `ALWAYS` as a "
            f"KernelNeed, not as a bare number here"
        )
    elif highest is not None:
        print(
            f"  ok: `{declared}` is exactly what the shipped files demand, not a number above them"
        )

    # 5 · Re-measure each need instead of trusting the table in the docstring: PRESENT at its
    #     release, ABSENT at the one before it.
    for need in sorted({n for n, _ in demanded}):
        at_floor, measured = (
            marker_count(f"v{dotted(need.floor)}", need.path, need.marker),
            (f"v{dotted(need.floor)}"),
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
        # `last_without` has to be the release RIGHT BEFORE the floor, or the pair proves nothing
        # about the releases in between. Measured in review of whatsapp_inbox#70: a need's floor
        # raised one release above where its marker first appears stayed green — the marker IS at
        # the higher release, and 0x at a `last_without` two releases back — because the module's
        # own floor was already justified by another need, so nothing said this one lied.
        predecessor = newest_tag_below(need.floor)
        if at_floor is None or before is None:
            print(
                f"  ⚠ SKIPPED the re-measure of {need.issue}: cannot read `{need.path}` at "
                f"{measured}/{need.last_without} from {HUB_CHECKOUT} (no hub checkout, or its tags "
                "are not fetched). The checks above still ran."
            )
        elif predecessor is not None and predecessor != need.last_without:
            failures.append(
                f"{need.issue} puts its floor at {dotted(need.floor)} and names {need.last_without} "
                f"as the last release without `{need.marker}`, but {predecessor} is the release "
                f"right before that floor and this pair never measures it: either the floor is a "
                f"release too high — the marker may already be there — or `last_without` is "
                f"stale. Re-derive both against `git tag --list` of the hub"
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
    if not predicates_proved:
        failures.append(
            "the floor derivations were never proved to discriminate: nothing called "
            "`predicate_self_check()`, so `PREDICATE_CASES` is a table nobody reads and every "
            "`FEATURES` predicate is back to being justified by today's documents alone"
        )
    if failures:
        print(f"\nFAIL ({len(failures)}):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(
        "\nOK: an old hub is told to update instead of installing an automation it cannot run"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

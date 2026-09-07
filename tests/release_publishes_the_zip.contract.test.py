#!/usr/bin/env python3
"""Everything that only reaches a hub inside the zip publishes a version (#80).

WHY THIS FILE EXISTS. `.github/workflows/release.yml` is what bumps the patch, and the bump is the
ONLY thing that republishes: the SaaS uploads `modules/{id}/v{version}.zip` create-only, so a merge
that does not raise the version finds the object already there and skips the upload (the header of
`release.yml` spells it out). The workflow only runs on the `paths:` it enumerates — so a path that
ships inside the zip and is NOT enumerated merges green, closes its issue, and reaches no business.

That is not hypothetical. Measured on `origin/main` the day #80 was written: nine of the ten merges
that touched `flows/` touched nothing else in `paths:`, and `gh run list --workflow release.yml`
has no run for any of them. `c4b5368` — the tip, an edit to the automation's own prompts — left the
module at v2.1.38, the version two merges older, and every installed hub kept the previous template.

WHAT THIS PINS:

  1. every packed path present in this repo is a trigger path of `release.yml` — parsed out of the
     `on.push.paths:` block, not grepped, so a mention inside the file's long comment header (it
     names `module.json` and `locales/**`) cannot pass for a real entry;
  2. except the two the SaaS refreshes on EVERY sync (below), which reach the marketplace by
     another door and would only inflate the version;
  3. and the packed list itself is RE-READ from the toolkit that builds the zip instead of trusted
     here: a folder that starts shipping tomorrow shows up as red in this module the same day,
     which is the half of the failure a hardcoded list cannot see.

THE EXEMPTION, MEASURED (2026-09-07, `saas`, `.../modules/repository/services.py:1730`):

    # Refresh README/CHANGELOG on EVERY sync, before deciding whether to upload.

`sync_module_repository` writes `module.readme` / `module.changelog` (and the translated fields)
before the create-only branch, precisely so that fixing a README reaches the ficha with no bump.
The hub never reads either file. Adding them to `paths:` would bump the version for a typo and
publish nothing new — so they are exempt ON PURPOSE, and the reason travels with the exemption.

Usage: tests/release_publishes_the_zip.contract.test.py   (exit 0 = green). No Postgres, no Docker.
"""

import pathlib
import re
import subprocess
import sys

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW = MODULE_DIR / ".github" / "workflows" / "release.yml"

# What `erplora pack` puts in the zip — `INCLUDE` in module-toolkit `src/pack.mjs`. Copied here so
# the check runs with no neighbours (the gate unpacks the module alone); check 3 re-reads the real
# one and fails when the two drift.
PACKED = (
    "module.json",
    "README.md",
    "CHANGELOG.md",
    "dist",
    "migrations",
    "queries",
    "commands",
    "schemas",
    "locales",
    "flows",
)

# Packed, but NOT a trigger path on purpose — see the docstring: the SaaS refreshes these on every
# sync, so they reach the marketplace ficha without a version and the hub never opens them.
REFRESHED_EVERY_SYNC = {"README.md", "CHANGELOG.md"}

# Sibling checkout of ERPlora/module-toolkit in the monorepo (`modules-workspace/modules/<id>` → root).
TOOLKIT_CHECKOUT = MODULE_DIR.parent.parent.parent / "module-toolkit"
TOOLKIT_PACK = "src/pack.mjs"

failures: list[str] = []


def trigger_paths(text: str) -> list[str] | None:
    """The entries of `on:` → `push:` → `paths:`. `None` when the block is not there at all.

    Hand-parsed on purpose: `pyyaml` is not in the gate's image, and a regex over the whole file
    would happily match the `paths` names quoted in the comment header above `on:`.
    """
    lines = text.splitlines()
    inside, indent, found = False, None, None
    for raw in lines:
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        depth = len(line) - len(line.lstrip())
        if inside:
            if depth <= indent:
                break
            item = line.strip()
            if item.startswith("- "):
                found.append(item[2:].strip().strip("'\""))
            continue
        if re.fullmatch(r"\s*paths:\s*", line):
            inside, indent, found = True, depth, []
    return found


def git(*args: str) -> subprocess.CompletedProcess | None:
    """`git -C <toolkit> …`, or `None` when git itself cannot be run."""
    try:
        return subprocess.run(
            ["git", "-C", str(TOOLKIT_CHECKOUT), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None


def packed_in_toolkit() -> tuple[list[str] | None, str | None]:
    """`INCLUDE` at the toolkit's trunk, as `(paths, reason_it_could_not_be_read)`.

    The two ways of not reading it are NOT the same and must not both go quiet. No checkout (or no
    fetched `origin/main`) is the gate unpacking this module on its own: nothing the author can act
    on, so it skips out loud. But a checkout that DOES resolve `origin/main` and still has no
    `src/pack.mjs` means the file moved — and a re-read pointed at a file that is not there is a
    check that passes for the rest of time without looking at anything. That one is a failure.
    """
    blob = git("show", f"origin/main:{TOOLKIT_PACK}")
    if blob is None:
        return None, "git could not be run"
    if blob.returncode != 0:
        if not TOOLKIT_CHECKOUT.is_dir():
            return None, f"there is no checkout at {TOOLKIT_CHECKOUT}"
        head = git("rev-parse", "--verify", "--quiet", "origin/main")
        if head is None or head.returncode != 0:
            return None, f"{TOOLKIT_CHECKOUT} has no fetched `origin/main`"
        failures.append(
            f"`{TOOLKIT_PACK}` is not at origin/main of {TOOLKIT_CHECKOUT} "
            f"({(head.stdout or '').strip()[:7]}), but the checkout is right there: the file that "
            "decides what goes in the zip moved, so the re-read below has been judging nothing. "
            "Point `TOOLKIT_PACK` at where `INCLUDE` lives now"
        )
        return None, None
    block = re.search(r"export const INCLUDE = \[(.*?)\]", blob.stdout, re.S)
    if block is None:
        failures.append(
            f"no `export const INCLUDE = [...]` in `{TOOLKIT_PACK}` at origin/main of "
            f"{TOOLKIT_CHECKOUT}: the packed list is declared some other way now and this re-read "
            "cannot see it any more"
        )
        return None, None
    return re.findall(r"['\"]([^'\"]+)['\"]", block[1]), None


def covers(entry: str, listed: set[str]) -> bool:
    """A packed path is covered by its own name (`module.json`) or by its glob (`flows/**`)."""
    return entry in listed or f"{entry}/**" in listed


def main() -> int:
    print("· what ships inside the zip publishes a version (whatsapp_inbox#80)")

    if not WORKFLOW.exists():
        failures.append(
            f"there is no `{WORKFLOW.relative_to(MODULE_DIR)}`, so nothing bumps the version and "
            "NOTHING this module changes ever reaches an installed hub: the SaaS only uploads "
            "`modules/{id}/v{version}.zip` when that version does not exist yet"
        )
        return report()

    listed = trigger_paths(WORKFLOW.read_text())
    if listed is None:
        failures.append(
            "`release.yml` declares no `on.push.paths:` block. Either it runs on every push (and "
            "the comment header explaining the filter is a lie) or the block was renamed — this "
            "control cannot judge what it cannot read"
        )
        return report()
    print(f"  ok: `on.push.paths:` lists {len(listed)} entries")

    # 1 + 2 · every packed path that lives in this repo is a trigger path.
    present = [p for p in PACKED if (MODULE_DIR / p).exists()]
    shipped = [p for p in present if p not in REFRESHED_EVERY_SYNC]
    exempt = [p for p in present if p in REFRESHED_EVERY_SYNC]
    for entry in shipped:
        if not covers(entry, set(listed)):
            failures.append(
                f"`{entry}` travels inside the zip but is not in `on.push.paths:`, so a merge that "
                f"touches only `{entry}` bumps no version — the marketplace keeps serving the "
                "previous zip and no installed hub is offered the change. Add "
                f"`- '{entry}/**'` to the `paths:` block of `.github/workflows/release.yml`"
            )
    if not failures:
        print(
            f"  ok: the {len(shipped)} packed paths that only travel in the zip are covered "
            f"({', '.join(shipped)}); exempt: {', '.join(exempt) or 'none'}"
        )

    # 3 · re-read the packed list from the toolkit that builds the zip.
    upstream, skipped = packed_in_toolkit()
    if skipped:
        print(
            f"  ⚠ SKIPPED the re-read of `{TOOLKIT_PACK}`: {skipped}. The checks above still ran "
            "against the copy in this file."
        )
    elif upstream is None:
        pass  # already reported: the file moved, or `INCLUDE` is gone
    elif set(upstream) != set(PACKED):
        gained, lost = (
            sorted(set(upstream) - set(PACKED)),
            sorted(set(PACKED) - set(upstream)),
        )
        failures.append(
            f"`INCLUDE` in the toolkit's `{TOOLKIT_PACK}` no longer matches the copy in this file"
            + (f" — it now packs {gained}" if gained else "")
            + (f" — it no longer packs {lost}" if lost else "")
            + ". Update `PACKED` here and list any new folder in `release.yml`, or a path that "
            "starts shipping today reaches no hub tomorrow"
        )
    else:
        print(
            f"  ok: re-read — `INCLUDE` at the toolkit's origin/main is the same {len(upstream)} paths"
        )

    return report()


def report() -> int:
    if failures:
        print(f"\nFAIL ({len(failures)}):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("\nOK: a merge that touches only what ships publishes a new version")
    return 0


if __name__ == "__main__":
    sys.exit(main())

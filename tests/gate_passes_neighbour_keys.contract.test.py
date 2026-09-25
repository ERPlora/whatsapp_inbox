#!/usr/bin/env python3
"""Both doors of this module's gate hand it the neighbours' deploy keys — module-toolkit#343.

`flows/*.requires.json` put version floors on neighbouring modules, and `tests/flow_templates.test.py`
checks each floor by reading the neighbour's history NEXT TO this module. On CI the shared gate
(module-toolkit `module-gate.yml`) clones those neighbours with the `MODULES_DEPLOY_KEYS` secret —
but only if the stub passes it on. A stub that does not is a gate that goes red on every pull
request (the toolkit refuses to skip the floors), or, before #343, one that skipped them green.

The two stubs are the two doors: `module-gate.yml` (pull requests) and `release.yml` (the version
bump that publishes). Both call the shared gate and both must pass the secret.

Usage: tests/gate_passes_neighbour_keys.contract.test.py   (exit 0 = green)
"""

import pathlib
import re
import sys

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
GATE = "ERPlora/module-toolkit/.github/workflows/module-gate.yml@main"
STUBS = (".github/workflows/module-gate.yml", ".github/workflows/release.yml")


def job_calling_gate(text):
    """The lines of the job whose `uses:` is the shared gate, comments stripped, or None."""
    lines = [l for l in text.splitlines() if not l.strip().startswith("#")]
    for i, line in enumerate(lines):
        if line.strip() == f"uses: {GATE}":
            indent = len(line) - len(line.lstrip())
            start = i
            while start > 0 and len(lines[start - 1]) - len(lines[start - 1].lstrip()) >= indent:
                start -= 1
            end = i + 1
            while end < len(lines) and (
                not lines[end].strip() or len(lines[end]) - len(lines[end].lstrip()) >= indent
            ):
                end += 1
            return "\n".join(lines[start:end])
    return None


def problems():
    out = []
    if not sorted((MODULE_DIR / "flows").glob("*.requires.json")):
        return out
    for rel in STUBS:
        job = job_calling_gate((MODULE_DIR / rel).read_text())
        if job is None:
            out.append(f"{rel} does not call {GATE}")
            continue
        if not re.search(
            r"^\s*secrets:\s*(inherit\s*$|\n\s+MODULES_DEPLOY_KEYS:\s*\$\{\{\s*secrets\.MODULES_DEPLOY_KEYS\s*\}\})",
            job,
            re.M,
        ):
            out.append(
                f"{rel}: the job calling the shared gate does not pass MODULES_DEPLOY_KEYS — "
                "the recipes declare floors on neighbours and the gate cannot bring them without it"
            )
    return out


def self_check():
    """The rule must see a job WITHOUT the secret — a blind rule would stay green forever."""
    bare = f"jobs:\n  validate:\n    uses: {GATE}\n"
    wired = f"jobs:\n  validate:\n    uses: {GATE}\n    secrets: inherit\n"
    job_bare, job_wired = job_calling_gate(bare), job_calling_gate(wired)
    assert job_bare is not None and "secrets" not in job_bare, job_bare
    assert job_wired is not None and "secrets: inherit" in job_wired, job_wired


def main():
    self_check()
    found = problems()
    for p in found:
        print(f"FAIL  {p}")
    if found:
        return 1
    print("OK: both gate doors pass MODULES_DEPLOY_KEYS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

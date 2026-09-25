#!/usr/bin/env python3
"""The recipes are checked against the hub's `flow.schema.json` on CI too — whatsapp_inbox#214.

`tests/flow_templates.test.py` validates every `flows/*.flow.json` against the contract the hub
serves (`hub/schemas/flow.schema.json`). It used to find that file ONLY as the monorepo sibling
`../../../hub`, which a CI runner does not have — so on every pull request the layer printed
`SKIPPED flow.schema.json not found` and the battery stayed green: a recipe the hub would refuse on
`PUT /api/hub/flows` could merge unseen. The shared gate already holds a full hub checkout and
exports it as `ERPLORA_HUB_DIR` (module-toolkit#146).

The contract this file pins, run against the real battery in a subprocess:

1. A declared `ERPLORA_HUB_DIR` is THE schema, and it wins over the monorepo sibling.
2. A declared hub without the schema is red (`hub_schema_missing`), never a skip: the gate
   promised a hub and the promise broke.
3. On CI (`CI` set) with no hub anywhere, red (`hub_schema_missing`).
4. With a hub to check against, `jsonschema` missing is red too (`jsonschema_missing`).
5. A bare local checkout with no hub and no CI still skips LOUDLY — it is a laptop, not a gate.

Usage: tests/flow_schema_source.contract.test.py   (exit 0 = green)
"""

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
BATTERY = "tests/flow_templates.test.py"
# What a bare clone needs to run the battery; everything else (dist/, node_modules/, target/) is
# build output the battery never reads.
BARE_IGNORE = shutil.ignore_patterns(
    ".git", "node_modules", "dist", "target", "*.relevo.md"
)


def run(module_dir, env_overrides, drop=()):
    env = {
        k: v for k, v in os.environ.items() if k not in drop and k != "ERPLORA_HUB_DIR"
    }
    env.update(env_overrides)
    proc = subprocess.run(
        [sys.executable, str(module_dir / BATTERY)],
        cwd=module_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return proc.returncode, proc.stdout + proc.stderr


def fake_hub(root, schema):
    """A directory shaped like a hub checkout, carrying `schema` as its flow.schema.json."""
    (root / "schemas").mkdir(parents=True)
    if schema is not None:
        (root / "schemas" / "flow.schema.json").write_text(schema)
    return root


def problems():
    out = []
    with tempfile.TemporaryDirectory(prefix="wa214-") as tmp:
        tmp = pathlib.Path(tmp)
        permissive = fake_hub(tmp / "hub-permissive", "{}")
        refusing = fake_hub(tmp / "hub-refusing", '{"not": {}}')
        empty = fake_hub(tmp / "hub-empty", None)

        # 1) The declared hub is the one used, over the monorepo sibling.
        code, text = run(MODULE_DIR, {"ERPLORA_HUB_DIR": str(permissive)})
        used = f"SCHEMA  {permissive / 'schemas' / 'flow.schema.json'}"
        if code != 0 or used not in text:
            out.append(
                f"declared hub (permissive schema): expected exit 0 and `{used}`, got {code}:\n{text}"
            )
        code, text = run(MODULE_DIR, {"ERPLORA_HUB_DIR": str(refusing)})
        if code == 0:
            out.append(
                f"declared hub whose schema refuses everything: the battery stayed green:\n{text}"
            )

        # 2) A declared hub without the schema is red.
        code, text = run(MODULE_DIR, {"ERPLORA_HUB_DIR": str(empty)})
        if code == 0 or "[hub_schema_missing]" not in text:
            out.append(
                f"declared hub without flow.schema.json: expected red `[hub_schema_missing]`, got {code}:\n{text}"
            )

        # 4) jsonschema not importable while there IS a schema to check against.
        shim = tmp / "no-jsonschema"
        shim.mkdir()
        (shim / "jsonschema.py").write_text(
            "raise ImportError('shimmed out by #214')\n"
        )
        code, text = run(
            MODULE_DIR, {"ERPLORA_HUB_DIR": str(permissive), "PYTHONPATH": str(shim)}
        )
        if code == 0 or "[jsonschema_missing]" not in text:
            out.append(
                f"hub declared, jsonschema missing: expected red `[jsonschema_missing]`, got {code}:\n{text}"
            )

        # 3) and 5) A bare clone, outside any monorepo — the CI runner's layout.
        bare = tmp / "runner" / "work" / "whatsapp_inbox"
        shutil.copytree(MODULE_DIR, bare, ignore=BARE_IGNORE)
        code, text = run(bare, {"CI": "true"})
        if code == 0 or "[hub_schema_missing]" not in text:
            out.append(
                f"bare clone on CI, no hub: expected red `[hub_schema_missing]`, got {code}:\n{text}"
            )
        code, text = run(bare, {}, drop=("CI",))
        if code != 0 or "SKIPPED" not in text or "flow.schema.json" not in text:
            out.append(
                f"bare local clone, no hub: expected a loud SKIPPED and exit 0, got {code}:\n{text}"
            )
    return out


def main():
    found = problems()
    for p in found:
        print(f"FAIL  {p}")
    if found:
        return 1
    print(
        "OK: the recipes are validated against the declared hub, and a missing hub on CI is red"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

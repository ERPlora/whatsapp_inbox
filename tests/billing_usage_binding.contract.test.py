#!/usr/bin/env python3
"""The month counter the «Plan» tab paints has to point at columns that EXIST (whatsapp_inbox#131).

`billing.usage` is four strings and nothing else: the query the shell calls, the metric it counts,
and the names of the two cells it reads out of the answer (`used`, `limit`). The shell takes those
names literally — `readModuleUsage` in the hub looks up `row[def.used]`, and when it cannot read a
non-negative number there it paints NOTHING, on purpose, because «NaN of 30» is a number a customer
believes (`apps/web/src/lib/module-usage.ts`, hub#1707).

So a typo in `used`, or an `AS` alias renamed in `queries/usage_get.sql` without the manifest
following, does not break anything loudly: the counter simply stops existing and the tab says «we
could not read what you have used». The business is back to learning it ran out of allowance because
WhatsApp went quiet, which is the whole defect whatsapp_inbox#131 existed to close.

🔴 Nothing else catches it. `erplora validate` reads the manifest schema for KEY NAMES only — there
is no ajv in the toolkit — so a `billing.usage` with a misspelled `used`, or missing it altogether
while the schema lists it as required, validates with output identical line by line to a correct one
(measured 09/09, module-toolkit#247). And the Postgres battery that runs the shipped query reads its
two cells by POSITION (`usage_reported` in `inbound_event_listener.pg.test.py`), so renaming an alias
leaves it green too. This file is the only place where the manifest's promise and the SQL that has to
keep it are compared.

Usage: tests/billing_usage_binding.contract.test.py   (exit 0 = green). No Postgres, no Docker.
"""

import json
import pathlib
import re
import sys

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())

# The keys `billing.usage` may not ship without, spelled as the manifest schema requires them
# (`schemas/module.schema.json` → `billing.properties.usage.required`). `limit` is optional there:
# a module whose cap lives only in the tier does not declare one. This one does, because the cap it
# enforces is the mirror the Cloud wrote (`free_tier_monthly_limit`), not the tier's figure.
REQUIRED_KEYS = ("query", "metric", "used")


def usage_block():
    block = MANIFEST.get("billing", {}).get("usage")
    return block if isinstance(block, dict) else None


def sql_of(query_name):
    """The SQL text(s) of a declared query — a plain path, or one per dialect."""
    declared = MANIFEST.get("queries", {}).get(query_name)
    if not isinstance(declared, dict):
        return None
    sql = declared.get("sql")
    rels = [sql] if isinstance(sql, str) else list(sql.values()) if isinstance(sql, dict) else []
    return [(rel, (MODULE_DIR / rel).read_text()) for rel in rels if isinstance(rel, str)]


def without_comments(sql):
    """The SQL with its `--` comments gone.

    The header of `usage_get.sql` explains the columns in prose, and a guard that accepted a name
    because the file MENTIONS it would keep passing after the alias itself was renamed — which is
    the one mutation this test is here for.
    """
    return "\n".join(re.sub(r"--.*$", "", line) for line in sql.splitlines())


def check_the_counter_is_declared_whole():
    """The block exists and carries the keys the shell needs to read anything at all."""
    block = usage_block()
    if block is None:
        return [
            "`billing.usage` is gone from the manifest: the «Plan» tab goes back to saying only what "
            "a plan INCLUDES, and the number that warns the channel is about to go quiet has no "
            "screen again (whatsapp_inbox#131, ADR-0470)"
        ]
    return [
        f"`billing.usage` has no `{key}`: the schema requires it and without it the shell cannot "
        "read the counter — it paints nothing rather than a number it cannot trust"
        for key in REQUIRED_KEYS
        if not isinstance(block.get(key), str) or not block[key].strip()
    ]


def check_the_query_is_one_this_module_declares():
    block = usage_block()
    if block is None or not isinstance(block.get("query"), str):
        return []
    name = block["query"]
    if name in MANIFEST.get("queries", {}):
        return []
    return [
        f"`billing.usage.query` is `{name}`, which this manifest does not declare: the shell would "
        "ask the dispatcher for a query that does not exist"
    ]


def check_every_declared_cell_is_a_column_of_the_answer():
    """`used` and `limit` have to be output aliases of the query the block names.

    Matched against the SQL with its comments stripped and on the `AS <alias>` form, because that is
    what decides the key the row arrives under: anything looser passes on a file that merely talks
    about the column.
    """
    block = usage_block()
    if block is None or not isinstance(block.get("query"), str):
        return []
    files = sql_of(block["query"])
    if not files:
        return []  # the query is not declared: already reported above

    problems = []
    for cell in ("used", "limit"):
        alias = block.get(cell)
        if not isinstance(alias, str) or not alias.strip():
            continue
        aliased = re.compile(rf'\bAS\s+"?{re.escape(alias)}"?\s*(?:,|;|$)', re.IGNORECASE | re.MULTILINE)
        for rel, sql in files:
            if aliased.search(without_comments(sql)):
                continue
            problems.append(
                f"`billing.usage.{cell}` is `{alias}` but `{rel}` returns no column by that name: "
                "the shell reads that cell out of the row by this exact name, finds nothing, and "
                "paints «we could not read what you have used» instead of the counter"
            )
    return problems


def main():
    problems = check_the_counter_is_declared_whole()
    problems += check_the_query_is_one_this_module_declares()
    problems += check_every_declared_cell_is_a_column_of_the_answer()

    for problem in problems:
        print(f"FAIL  {problem}")
    if problems:
        print(f"\n{len(problems)} broken promise(s) in `billing.usage`")
        return 1

    block = usage_block()
    cells = [c for c in ("used", "limit") if block.get(c)]
    print(
        f"OK: `{block['query']}` answers the «Plan» tab with "
        f"{', '.join(f'`{block[c]}`' for c in cells)} — every cell it promises is a column it returns"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

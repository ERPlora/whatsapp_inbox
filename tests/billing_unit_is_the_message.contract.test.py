#!/usr/bin/env python3
"""One unit: what we sell, what we count and what cuts the channel have to be the same thing
(whatsapp_inbox#147, re-creation of whatsapp_inbox#13).

The «Plan» tab paints `used` out of `limit` and puts the metric's label after it, so the sentence a
salon owner reads is «24 of 30 <unit>». Three different files decide that sentence and NONE of them
can see the other two:

  * the CATALOG — `billing.tiers[].quota.<metric>` — names the unit and its allowance;
  * the COUNTER — `queries/usage_get.sql`, behind `billing.usage.used` — produces the 24;
  * the two INGEST GUARDS — the commands that compare that same count against
    `whatsapp_inbox_settings.free_tier_monthly_limit` — decide when WhatsApp goes quiet.

Until this guard existed they disagreed, and the disagreement shipped: the catalog sold
`conversations_per_month` while all three counting expressions were `COUNT(*)` over
`whatsapp_inbox_message`. Measured against Postgres with the shipped SQL — one client writing six
times to book one appointment is ONE conversation and SIX units of the counter, so the tab told a
salon it had spent 24 of 30 after eight clients, and the channel then went quiet at a number the
owner had no way to predict. Nobody could see it: the number is CORRECT for what stops the channel,
only the noun is wrong, and a wrong noun renders exactly like a right one.

The unit is the MESSAGE, and it is not our invention: Meta itself replaced conversation-based
pricing with per-message pricing on 1 July 2025, and the Cloud already migrated its own tier rows to
`billable_messages_per_month` (`saas/apps/whatsapp_inbox/migrations/0003_billable_message_pricing`).
The manifest is what re-seeds `ModuleTier.quota` on every catalog sync, so a conversation key here
does not merely mislabel the tab — it writes the Cloud's migration back out.

So this file does not check a spelling. It DERIVES the unit from the SQL that actually counts, and
then demands that the catalog, the counter's metric and every ingest guard all say that one. Change
the counter to conversations and the metric stops matching; change one guard and it stops matching
the counter; sell a second unit and the catalog stops matching both.

Usage: tests/billing_unit_is_the_message.contract.test.py   (exit 0 = green). No Postgres, no Docker.
"""

import json
import pathlib
import re
import sys

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())

# The column the Cloud writes with the allowance it resolved (`whatsapp_inbox._quota.set`). Every
# statement that compares a count against it is, by definition, a guard that can silence the
# channel — which is how they are found here instead of being listed by name: a third one added
# tomorrow is covered the day it is written, not the day somebody remembers this file.
ENFORCEMENT_COLUMN = "free_tier_monthly_limit"

# The nouns a metric key may claim, and the counting shape that earns each of them. A shape absent
# from this table is not assumed innocent: it is reported, because a counter nobody can name is a
# counter nobody can label honestly.
UNIT_OF_SHAPE = {
    ("whatsapp_inbox_message", "*"): "message",
    ("whatsapp_inbox_message", "distinct m.conversation_id"): "conversation",
    ("whatsapp_inbox_message", "distinct conversation_id"): "conversation",
    ("whatsapp_inbox_conversation", "*"): "conversation",
}

# Every noun this project meters anything in. A metric may contain its own and no other: the defect
# this file closes was a key naming one unit while the SQL counted a different one.
KNOWN_UNITS = ("message", "conversation", "contact", "session", "request")


def strip_comments(sql):
    """SQL without its `--` comments.

    The counting subqueries carry long explanations that name columns and units in prose; matching
    against them would let a rename pass because the file still TALKS about the old shape.
    """
    return "\n".join(re.sub(r"--.*$", "", line) for line in sql.splitlines())


def counting_selects(sql):
    """Every `SELECT COUNT(...) FROM <table> WHERE <predicates>` in `sql`, parens balanced.

    Returns one dict per counter with the three things that decide WHAT it counts: the expression
    inside COUNT, the table it walks, and the set of its WHERE predicates.
    """
    text = strip_comments(sql)
    found = []
    for match in re.finditer(r"\bSELECT\s+COUNT\s*\(", text, re.IGNORECASE):
        depth, end = 0, len(text)
        for i in range(match.end() - 1, len(text)):
            ch = text[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i > match.end() - 1 and text[i] == ")":
                    # closing paren of COUNT(...) itself keeps depth at 0 afterwards
                    pass
                if depth < 0:
                    end = i
                    break
            elif ch == ";" and depth == 0:
                end = i
                break
        body = text[match.start():end]
        counted = re.search(r"COUNT\s*\(([^)]*)\)", body, re.IGNORECASE)
        table = re.search(r"\bFROM\s+([A-Za-z_][A-Za-z0-9_]*)", body, re.IGNORECASE)
        where = re.search(r"\bWHERE\b(.*)", body, re.IGNORECASE | re.DOTALL)
        found.append(
            {
                "counted": " ".join((counted.group(1) if counted else "").split()).lower(),
                "table": (table.group(1) if table else "").lower(),
                "predicates": predicates_of(where.group(1) if where else ""),
                "body": body,
                # What the count is weighed against. A guard whose comparison drifted off the
                # allowance column still counts perfectly and never stops anything.
                "compared_to": " ".join(text[end:end + 90].split()),
            }
        )
    return found


def predicates_of(where_clause):
    """The WHERE clause as a comparable set of atoms, whitespace and table alias normalised.

    Compared as a SET so the three statements may order their predicates differently — they do —
    while any predicate ADDED to or DROPPED from one of them still shows up.
    """
    atoms = set()
    for atom in re.split(r"\bAND\b", where_clause, flags=re.IGNORECASE):
        atom = " ".join(atom.split()).strip().rstrip(")").strip()
        if not atom:
            continue
        atoms.add(re.sub(r"\bm\.", "", atom).lower())
    return atoms


def shape_of(counter):
    return (counter["table"], counter["counted"])


def usage_block():
    block = MANIFEST.get("billing", {}).get("usage")
    return block if isinstance(block, dict) else {}


def sql_paths_of_query(query_name):
    declared = MANIFEST.get("queries", {}).get(query_name)
    if not isinstance(declared, dict):
        return []
    sql = declared.get("sql")
    rels = [sql] if isinstance(sql, str) else list(sql.values()) if isinstance(sql, dict) else []
    return [rel for rel in rels if isinstance(rel, str)]


def the_counter():
    """The counting subquery the «Plan» tab actually reads, i.e. the one aliased as `usage.used`."""
    block = usage_block()
    alias = block.get("used")
    if not isinstance(alias, str) or not alias.strip():
        return None, "`billing.usage.used` is missing: there is no counter to compare anything to"
    for rel in sql_paths_of_query(block.get("query")):
        sql = strip_comments((MODULE_DIR / rel).read_text())
        aliased = re.search(rf'\bAS\s+"?{re.escape(alias)}"?', sql, re.IGNORECASE)
        if not aliased:
            continue
        # The counter is the last counting SELECT that opens before its own alias.
        candidates = [c for c in counting_selects(sql) if sql.find(c["body"]) < aliased.start()]
        if candidates:
            return candidates[-1], None
    return None, (
        f"no counting subquery in `{usage_block().get('query')}` is aliased `{alias}` — the tab "
        "reads that cell by name and would paint nothing"
    )


def weighed_against_the_allowance(counter):
    """True when this count is compared against the column the Cloud writes the allowance into."""
    return bool(
        re.match(
            rf"\)?\s*(?:>=|>|<=|<|=)\s*[A-Za-z_][A-Za-z0-9_]*\.{ENFORCEMENT_COLUMN}\b",
            counter["compared_to"],
        )
    )


def the_ingest_guards():
    """Every command SQL count that is actually weighed against the Cloud's allowance column."""
    guards, unweighed = [], []
    for path in sorted((MODULE_DIR / "commands").glob("*.sql")):
        text = strip_comments(path.read_text())
        if ENFORCEMENT_COLUMN not in text:
            continue
        for counter in counting_selects(text):
            (guards if weighed_against_the_allowance(counter) else unweighed).append(
                (path.name, counter)
            )
    return guards, unweighed


def catalog_metrics():
    metrics = []
    for tier in MANIFEST.get("billing", {}).get("tiers", []):
        for metric in (tier.get("quota") or {}):
            if metric not in metrics:
                metrics.append(metric)
    return metrics


def check_every_guard_counts_what_the_counter_counts(counter):
    """The number on screen and the number that silences WhatsApp must be one number.

    Not «both are message counts» — the SAME count. A predicate present in the guard and absent
    from the counter (or the other way round) is a tab that reassures a business right up to the
    minute its channel stops, which is the failure whatsapp_inbox#131 already paid for once.
    """
    problems = []
    guards, unweighed = the_ingest_guards()
    for name, stray in unweighed:
        problems.append(
            f"{name}: this command counts `COUNT({stray['counted']})` over `{stray['table']}` but "
            f"weighs it against `{stray['compared_to'][:40].strip()}` instead of "
            f"`{ENFORCEMENT_COLUMN}` — it would count the month perfectly and never stop anything, "
            "so the allowance is sold and never applied"
        )
    if not guards:
        return [
            f"no command compares a count against `{ENFORCEMENT_COLUMN}`: nothing enforces the "
            "allowance the Cloud resolved, so the plan is sold and never applied"
        ]
    for name, guard in guards:
        if shape_of(guard) != shape_of(counter):
            problems.append(
                f"{name}: the guard counts `COUNT({guard['counted']})` over "
                f"`{guard['table']}` while the «Plan» tab counts `COUNT({counter['counted']})` "
                f"over `{counter['table']}` — the business would watch one number and be cut off "
                "by another"
            )
            continue
        for extra in sorted(guard["predicates"] - counter["predicates"]):
            problems.append(
                f"{name}: the guard narrows the count with `{extra}` and the «Plan» tab does not — "
                "the tab would read HIGHER than the number that cuts the channel"
            )
        for missing in sorted(counter["predicates"] - guard["predicates"]):
            problems.append(
                f"{name}: the «Plan» tab narrows the count with `{missing}` and this guard does "
                "not — the channel would go quiet while the tab still shows allowance left"
            )
    return problems


def check_the_metric_names_the_unit_the_sql_counts(counter):
    """The noun on screen has to be the noun the SQL produced."""
    unit = UNIT_OF_SHAPE.get(shape_of(counter))
    if unit is None:
        return [
            f"the counter is `COUNT({counter['counted']})` over `{counter['table']}`, a shape this "
            "guard cannot name — add it to UNIT_OF_SHAPE with the noun it produces, because a "
            "counter nobody can name cannot be labelled honestly on the «Plan» tab"
        ]
    problems = []
    metric = usage_block().get("metric")
    if not isinstance(metric, str) or not metric.strip():
        return ["`billing.usage.metric` is missing: the counter would be a number with no unit"]
    for name in [metric] + catalog_metrics():
        claimed = [u for u in KNOWN_UNITS if u in name]
        if unit not in claimed:
            problems.append(
                f"`{name}` does not name the `{unit}` the SQL counts — the «Plan» tab would put "
                f"the month's {unit} count under a unit this module does not measure"
            )
        for wrong in claimed:
            if wrong != unit:
                problems.append(
                    f"`{name}` sells `{wrong}s` while the counter and both ingest guards count "
                    f"`{unit}s` — this is exactly the mismatch whatsapp_inbox#13 was closed "
                    "without fixing, and whatsapp_inbox#147 re-opened"
                )
    return problems


def check_the_catalog_sells_the_metric_the_counter_reports():
    """One unit, not two: every tier has to sell the same metric the counter reports."""
    metric = usage_block().get("metric")
    metrics = catalog_metrics()
    if not isinstance(metric, str) or not metrics:
        return []
    return [
        f"the tiers sell {sorted(set(metrics))} but the counter reports `{metric}`: the «Plan» tab "
        "would show consumption of one unit under the allowance of another"
        for _ in [None]
        if set(metrics) != {metric}
    ]


def main():
    counter, failure = the_counter()
    if counter is None:
        print(f"FAIL  {failure}")
        return 1

    problems = check_every_guard_counts_what_the_counter_counts(counter)
    problems += check_the_metric_names_the_unit_the_sql_counts(counter)
    problems += check_the_catalog_sells_the_metric_the_counter_reports()

    for problem in problems:
        print(f"FAIL  {problem}")
    if problems:
        print(f"\n{len(problems)} place(s) where the unit sold is not the unit counted")
        return 1

    unit = UNIT_OF_SHAPE[shape_of(counter)]
    print(
        f"OK: one unit end to end — the catalog sells `{usage_block()['metric']}`, the counter "
        f"and {len(the_ingest_guards()[0])} ingest guard(s) all count {unit}s the same way"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""One unit and ONE meter: what we sell, what the tab paints and what cuts the channel have to be
the same number (whatsapp_inbox#147, re-creation of #13, rebuilt on #155).

The «Plan» tab paints `used` out of `limit` and puts the metric's label after it, so the sentence a
salon owner reads is «24 of 30 <unit>». Three files decide that sentence and none of them can see
the other two:

  * the CATALOG — `billing.tiers[].quota.<metric>` — names the unit and its allowance;
  * the COUNTER — `queries/usage_get.sql`, behind `billing.usage.used` — produces the 24;
  * the two INGEST GUARDS — the commands that weigh that number against
    `whatsapp_inbox_settings.free_tier_monthly_limit` — decide when WhatsApp goes quiet.

## The two ways they have drifted apart, and why this file checks what it checks

**The noun (whatsapp_inbox#13/#147).** The catalog sold `conversations_per_month` while all three
counting expressions were `COUNT(*)` over `whatsapp_inbox_message`. One client writing six times to
book one appointment is ONE conversation and SIX units of the counter, so the tab told a salon it
had spent 24 of 30 after eight clients and the channel then went quiet at a number the owner had no
way to predict. Nobody could see it: the number was CORRECT for what stopped the channel, only the
noun was wrong, and a wrong noun renders exactly like a right one. The unit is the MESSAGE, and it
is not our invention — Meta replaced conversation-based pricing with per-message pricing on 1 July
2025, and the Cloud migrated its own tier rows to `billable_messages_per_month`. The manifest is
what re-seeds `ModuleTier.quota` on every catalog sync, so a conversation key here does not merely
mislabel the tab: it writes the Cloud's migration back out.

**The number itself (whatsapp_inbox#155).** Counting locally was the deeper half of the same
defect, because the messages this module can count are the ones that come IN and what is sold — and
what Meta charges ERPlora for — are the ones the business SENDS. The platform already meters that
and shows it to the owner on erplora.com, so one allowance had two meters and the owner could read
«4 of 30» in their account with the channel already cut in their hub, both true. The spend now
arrives through the same internal door as the cap (`whatsapp_inbox._quota.set`, whatsapp_inbox#37)
and is stored on the settings singleton; the tab and both guards read that one stored figure.

## So what is asserted

1. **The tab and every guard read the SAME expression**, compared as text with aliases and
   whitespace normalised — not «both look at the meter», the same expression. A month gate present
   in one and absent from the other is a tab that reassures a business right up to the minute its
   channel stops.
2. **Nobody counts rows against the allowance any more.** A `COUNT(` back in the counter or in a
   guard is the two-meter defect returning, and it renders identically to a correct one.
3. **The columns that expression reads are the platform's**: among this module's commands, only
   the door that writes the cap may write them. A second writer is a hub editing its own invoice.
4. **The expression carries both halves** — the figure and the month it counts. Dropping the stamp
   leaves a business that ended the month at its cap shut for up to a day of the next one.
5. **The catalog, the metric and the unit still agree**, which is the original #13 check.

Usage: tests/billing_unit_is_the_message.contract.test.py   (exit 0 = green). No Postgres, no Docker.
"""

import json
import pathlib
import re
import sys

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())

# The column the Cloud writes the allowance into (`whatsapp_inbox._quota.set`). Every statement
# that weighs something against it is, by definition, a guard that can silence the channel — which
# is how the guards are FOUND here instead of being listed by name: a third one added tomorrow is
# covered the day it is written, not the day somebody remembers this file.
ENFORCEMENT_COLUMN = "free_tier_monthly_limit"

# The table the meter lives on. Used to tell a WRITER of the meter from a READER: the guards name the
# meter columns too, but they INSERT into the message table.
SETTINGS_TABLE = "whatsapp_inbox_settings"

# The unit the platform bills in, and every noun this project meters anything in. A metric may
# contain its own and no other: the defect this file closes was a key naming one unit while the
# number came from another.
BILLED_UNIT = "message"
KNOWN_UNITS = ("message", "conversation", "contact", "session", "request")


def strip_comments(sql):
    """SQL without its `--` comments.

    These files carry long explanations that name columns and units in prose; matching against them
    would let a rename pass because the file still TALKS about the old shape.
    """
    return "\n".join(re.sub(r"--.*$", "", line) for line in sql.splitlines())


def normalise(expression):
    """An expression as its meaning: whitespace collapsed, aliases dropped, case folded.

    The tab wraps its copy in `COALESCE((SELECT … LIMIT 1), 0)` and the guards do not, and they
    qualify the columns differently (`s.` here, the table name there). None of that changes what is
    being weighed, and all of it would make two identical rules look different.
    """
    text = " ".join(expression.split()).lower()
    text = re.sub(rf"\b{SETTINGS_TABLE}\.", "", text)
    text = re.sub(r"\b[a-z_][a-z0-9_]*\.(?=[a-z_])", "", text)
    return re.sub(r"\s+", " ", text).strip()


def case_expression(text, start=0):
    """The first balanced `CASE … END` in `text` at or after `start`, or None.

    Both readers express the month gate as one CASE, so this is the comparable core of each of
    them: the tab's wrapper and the guard's `AND` are packaging, the CASE is the rule.
    """
    opened = re.search(r"\bCASE\b", text[start:], re.IGNORECASE)
    if not opened:
        return None
    begin = start + opened.start()
    depth = 0
    for token in re.finditer(r"\b(CASE|END)\b", text[begin:], re.IGNORECASE):
        depth += 1 if token.group(1).upper() == "CASE" else -1
        if depth == 0:
            return text[begin : begin + token.end()]
    return None


def sql_paths_of_query(query_name):
    declared = MANIFEST.get("queries", {}).get(query_name)
    if not isinstance(declared, dict):
        return []
    sql = declared.get("sql")
    rels = (
        [sql]
        if isinstance(sql, str)
        else list(sql.values())
        if isinstance(sql, dict)
        else []
    )
    return [rel for rel in rels if isinstance(rel, str)]


def usage_block():
    block = MANIFEST.get("billing", {}).get("usage")
    return block if isinstance(block, dict) else {}


def the_counter():
    """The expression the «Plan» tab actually reads, i.e. the one aliased as `usage.used`."""
    block = usage_block()
    alias = block.get("used")
    if not isinstance(alias, str) or not alias.strip():
        return (
            None,
            "`billing.usage.used` is missing: there is no counter to compare anything to",
        )
    for rel in sql_paths_of_query(block.get("query")):
        sql = strip_comments((MODULE_DIR / rel).read_text())
        aliased = re.search(rf'\bAS\s+"?{re.escape(alias)}"?', sql, re.IGNORECASE)
        if not aliased:
            continue
        expression = sql[: aliased.start()]
        core = case_expression(expression)
        # The last CASE that opens before the alias is the one this cell is built from.
        while core is not None:
            following = case_expression(expression, expression.find(core) + len(core))
            if following is None:
                break
            core = following
        if core is None:
            return None, (
                f"`{rel}` aliases `{alias}` but the cell is not built from a `CASE … END`: the tab "
                "and the guards can no longer be compared as one rule, and the month gate that "
                "keeps a new month from inheriting the last one has nowhere to live"
            )
        return {"rel": rel, "core": core, "expression": expression}, None
    return None, (
        f"no column of `{block.get('query')}` is aliased `{alias}` — the tab reads that cell by "
        "name and would paint nothing"
    )


def the_ingest_guards():
    """Every command that weighs something against the Cloud's allowance column."""
    guards, unreadable = [], []
    for path in sorted((MODULE_DIR / "commands").glob("*.sql")):
        text = strip_comments(path.read_text())
        # A command that WRITES the meter names the column on the left of an `=` and is not a
        # guard: `_quota.set` carries `free_tier_monthly_limit = excluded.free_tier_monthly_limit`
        # in its ON CONFLICT, which is the allowance arriving, not the channel being weighed.
        if re.search(
            rf"\b(?:INSERT\s+INTO|UPDATE)\s+{SETTINGS_TABLE}\b", text, re.IGNORECASE
        ):
            continue
        weighed = re.search(
            rf"(?:>=|>|<=|<|=)\s*(?:[A-Za-z_][A-Za-z0-9_]*\.)?{ENFORCEMENT_COLUMN}\b",
            text,
        )
        if not weighed:
            continue
        before = text[: weighed.start()]
        core = case_expression(before)
        while core is not None:
            following = case_expression(before, before.find(core) + len(core))
            if following is None:
                break
            core = following
        if core is None:
            unreadable.append((path.name, before))
            continue
        guards.append({"name": path.name, "core": core, "before": before})
    return guards, unreadable


def writers_of(column):
    """The command SQL files that WRITE `column` — i.e. whose statement targets the meter's table.

    A guard NAMES the meter columns too, but it inserts into `whatsapp_inbox_message`: reading the
    invoice is the whole point, writing it is the hole whatsapp_inbox#37 closed.
    """
    found = []
    for path in sorted((MODULE_DIR / "commands").glob("*.sql")):
        text = strip_comments(path.read_text())
        targets = re.search(
            rf"\b(?:INSERT\s+INTO|UPDATE)\s+{SETTINGS_TABLE}\b", text, re.IGNORECASE
        )
        if targets and re.search(rf"\b{column}\b", text):
            found.append(path.name)
    return found


def owner_door_files():
    spec = MANIFEST.get("commands", {}).get("whatsapp_inbox._quota.set")
    if not isinstance(spec, dict):
        return []
    sql = spec.get("sql")
    files = sql if isinstance(sql, list) else [sql]
    return [pathlib.Path(rel).name for rel in files if isinstance(rel, str)]


def meter_columns_of(core):
    """The settings columns the shared expression reads, derived from the migrations."""
    declared = set()
    for entry in MANIFEST.get("migrations", {}).get("postgres", []):
        rel = entry if isinstance(entry, str) else entry.get("file")
        text = strip_comments((MODULE_DIR / rel).read_text())
        for block in re.finditer(
            rf"(?:CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?|ALTER\s+TABLE)\s+{SETTINGS_TABLE}\b(.*?)(?:;|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        ):
            for column in re.finditer(
                r"(?:ADD\s+COLUMN(?:\s+IF\s+NOT\s+EXISTS)?\s+|^\s*|,\s*)([a-z_][a-z0-9_]*)\s+"
                r"(?:INTEGER|TEXT|NUMERIC|BOOLEAN)",
                block.group(1),
                re.IGNORECASE | re.MULTILINE,
            ):
                declared.add(column.group(1).lower())
    words = set(re.findall(r"[a-z_][a-z0-9_]*", normalise(core)))
    return sorted(declared & words)


def catalog_metrics():
    metrics = []
    for tier in MANIFEST.get("billing", {}).get("tiers", []):
        for metric in tier.get("quota") or {}:
            if metric not in metrics:
                metrics.append(metric)
    return metrics


def check_the_tab_and_every_guard_read_one_expression(counter):
    """(1) and (4): the number on screen and the number that silences WhatsApp are ONE rule."""
    problems = []
    guards, unreadable = the_ingest_guards()
    for name, _ in unreadable:
        problems.append(
            f"{name}: this command weighs something against `{ENFORCEMENT_COLUMN}` but not a "
            "`CASE … END` like the «Plan» tab does — the two can no longer be compared, so a guard "
            "that drifts off the tab's rule stops being visible here"
        )
    if not guards:
        return problems + [
            f"no command weighs anything against `{ENFORCEMENT_COLUMN}`: nothing enforces the "
            "allowance the Cloud resolved, so the plan is sold and never applied"
        ]

    wanted = normalise(counter["core"])
    for guard in guards:
        got = normalise(guard["core"])
        if got != wanted:
            problems.append(
                f"{guard['name']}: the guard weighs `{got}` while the «Plan» tab paints `{wanted}` "
                f"(`{counter['rel']}`) — the business would watch one number and be cut off by "
                "another"
            )

    columns = meter_columns_of(counter["core"])
    if len(columns) < 2:
        problems.append(
            f"the shared expression reads {columns or 'no settings column at all'}: it needs the "
            "spend AND the month it counts. The Cloud sync ticks once a day and the payload "
            "carries no month, so without the stamp a business that ended the month at its cap "
            "spends up to 24 h of the next one with the channel shut"
        )
    return problems


def check_nobody_counts_rows_against_the_allowance(counter):
    """(2) the two-meter defect returning, and it renders identically to a correct tab."""
    problems = []
    guards, _ = the_ingest_guards()
    for where, text in [(counter["rel"], counter["expression"])] + [
        (g["name"], g["before"]) for g in guards
    ]:
        if re.search(r"\bCOUNT\s*\(", text, re.IGNORECASE):
            problems.append(
                f"{where}: the allowance is weighed against a `COUNT(…)` again. This module can "
                "only count the messages that come IN, and what is sold — and what Meta charges "
                "ERPlora for — are the ones the business SENDS, so a local count is a second meter "
                "for one allowance (whatsapp_inbox#155)"
            )
    return problems


def check_the_meter_columns_belong_to_the_platform(counter):
    """(3) a hub that can write its own spend can write its own invoice."""
    problems = []
    owner = set(owner_door_files())
    if not owner:
        return ["`whatsapp_inbox._quota.set` is not declared: the meter has no owner"]
    for column in meter_columns_of(counter["core"]) + [ENFORCEMENT_COLUMN]:
        strangers = [name for name in writers_of(column) if name not in owner]
        if strangers:
            problems.append(
                f"`{column}` is written by {strangers} as well as by the internal door "
                f"{sorted(owner)}: the numbers on this row are the invoice, and a second writer is "
                "a hub — or the assistant acting for it — editing its own bill "
                "(whatsapp_inbox#37)"
            )
    return problems


def check_the_metric_names_the_unit_that_is_billed():
    """(5) the noun on screen has to be the noun that is charged for."""
    problems = []
    metric = usage_block().get("metric")
    if not isinstance(metric, str) or not metric.strip():
        return [
            "`billing.usage.metric` is missing: the counter would be a number with no unit"
        ]
    for name in [metric] + catalog_metrics():
        claimed = [unit for unit in KNOWN_UNITS if unit in name]
        if BILLED_UNIT not in claimed:
            problems.append(
                f"`{name}` does not name the `{BILLED_UNIT}` the platform bills — the «Plan» tab "
                "would put the month's billable messages under a unit nobody is charged in"
            )
        for wrong in claimed:
            if wrong != BILLED_UNIT:
                problems.append(
                    f"`{name}` sells `{wrong}s` while the platform counts `{BILLED_UNIT}s` — this "
                    "is exactly the mismatch whatsapp_inbox#13 was closed without fixing, and "
                    "whatsapp_inbox#147 re-opened"
                )
    return problems


def check_the_catalog_sells_the_metric_the_counter_reports():
    """One unit, not two: every tier has to sell the same metric the counter reports."""
    metric = usage_block().get("metric")
    metrics = catalog_metrics()
    if not isinstance(metric, str) or not metrics or set(metrics) == {metric}:
        return []
    return [
        f"the tiers sell {sorted(set(metrics))} but the counter reports `{metric}`: the «Plan» tab "
        "would show consumption of one unit under the allowance of another"
    ]


def main():
    counter, failure = the_counter()
    if counter is None:
        print(f"FAIL  {failure}")
        return 1

    problems = check_the_tab_and_every_guard_read_one_expression(counter)
    problems += check_nobody_counts_rows_against_the_allowance(counter)
    problems += check_the_meter_columns_belong_to_the_platform(counter)
    problems += check_the_metric_names_the_unit_that_is_billed()
    problems += check_the_catalog_sells_the_metric_the_counter_reports()

    for problem in problems:
        print(f"FAIL  {problem}")
    if problems:
        print(
            f"\n{len(problems)} place(s) where the unit sold is not the number that is applied"
        )
        return 1

    guards, _ = the_ingest_guards()
    print(
        f"OK: one meter end to end — the catalog sells `{usage_block()['metric']}`, and the «Plan» "
        f"tab and {len(guards)} ingest guard(s) read the one figure the platform wrote, with the "
        f"same expression over {meter_columns_of(counter['core'])}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

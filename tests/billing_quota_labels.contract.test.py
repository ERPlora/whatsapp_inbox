#!/usr/bin/env python3
"""Every quota metric this module sells has to be readable in every language it ships (hub#1604).

`billing.tiers[].quota` is a dict of `{ metric: limit }` and the metric is an identifier we write:
`conversations_per_month`. The hub's «Plan» tab paints it, and until hub#1604 it painted it by
swapping the underscores for spaces — so a salon owner on a Spanish hub read «Incluye 30
conversations per month», half the sentence in her language and half not, on the screen where she
decides how much to spend every month.

The shell cannot fix that on its own: only whoever wrote the manifest knows what
`conversations_per_month` means in Spanish. So the words live here, in `locales/<lang>.json` under
`billing.quota.<metric>` — the same place the module already translates its navigation, its widgets
and the fields of its settings screen (hub#1094).

This gate is what keeps them from drifting apart: add a tier with a new metric, or a language, and
the labels have to follow. English is the source language (ADR-0055), so a missing label degrades to
English rather than breaking — which is exactly why nobody would notice, and exactly why this test
exists.

`billing.usage.metric` names the SAME key space from the other side (whatsapp_inbox#131): it says
which of those quotas the month counter is counting, so the shell can write «12 of 30 conversations
per month» with the unit in the customer's language. It is checked here for both reasons — its label
has to exist like any other, and the metric has to be one the tiers actually sell, or the counter
sits under a cap nobody bought.

Usage: tests/billing_quota_labels.contract.test.py   (exit 0 = green). No Postgres, no Docker.
"""

import json
import pathlib
import sys

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())
LOCALES_DIR = MODULE_DIR / "locales"


def quota_metrics():
    """Every metric named by any tier of the manifest, in declaration order and without repeats."""
    metrics = []
    for tier in MANIFEST.get("billing", {}).get("tiers", []):
        quota = tier.get("quota")
        if not isinstance(quota, dict):
            continue
        for metric in quota:
            if metric not in metrics:
                metrics.append(metric)
    return metrics


def usage_metric():
    """The metric the month counter reports, or None if the module declares no counter."""
    usage = MANIFEST.get("billing", {}).get("usage")
    if not isinstance(usage, dict):
        return None
    return usage.get("metric")


def check_the_usage_metric_is_one_the_tiers_sell():
    """The counter has to count something a plan includes.

    `billing.usage` gives the shell `used` out of `limit`; `metric` is what turns that pair into a
    sentence. Naming a metric no tier declares is not a typo the customer can see through: the
    «Plan» tab would put the month's consumption under a unit no plan of this module sells, and the
    label check below would not even ask for its words, because it only walks the tiers.
    """
    metric = usage_metric()
    if metric is None:
        return []
    if metric in quota_metrics():
        return []
    return [
        f"`billing.usage.metric` is `{metric}`, which no tier's `quota` declares "
        f"(the tiers sell: {', '.join(quota_metrics()) or 'nothing'}) — the month counter would "
        f"report against a cap this module does not sell"
    ]


def locale_files():
    return sorted(LOCALES_DIR.glob("*.json"))


def check_every_metric_is_named_in_every_language():
    problems = []
    metrics = quota_metrics()
    if not metrics:
        return problems
    for path in locale_files():
        labels = json.loads(path.read_text()).get("billing", {}).get("quota", {})
        for metric in metrics:
            label = labels.get(metric)
            if label is None:
                problems.append(
                    f"{path.name}: no label for the quota metric `{metric}` — the plan screen "
                    f"would fall back to English"
                )
            elif not str(label).strip():
                problems.append(
                    f"{path.name}: the label for `{metric}` is blank — a number with no unit "
                    f"after it says less than the English it replaced"
                )
    return problems


def check_non_english_labels_are_translated():
    """English is the source language (ADR-0055): a non-English file whose label is the English
    one, character for character, is a copy-paste, not a translation. The test that only asks
    «is there a label?» stays green on it — and the customer reads English again (hub#1604)."""
    problems = []
    en_path = LOCALES_DIR / "en.json"
    if not en_path.is_file():
        return problems
    en_labels = json.loads(en_path.read_text()).get("billing", {}).get("quota", {})
    for path in locale_files():
        if path == en_path:
            continue
        labels = json.loads(path.read_text()).get("billing", {}).get("quota", {})
        for metric, label in labels.items():
            en_label = en_labels.get(metric)
            if en_label is None or not str(label).strip():
                continue  # already reported by the checks above
            if str(label).strip().casefold() == str(en_label).strip().casefold():
                problems.append(
                    f"{path.name}: the label for `{metric}` is the English one (`{en_label}`) — "
                    f"translate it, or the plan screen reads in English on a {path.stem} hub"
                )
    return problems


def check_no_label_survives_its_metric():
    """A label for a metric no tier sells any more is a leftover: it says the plan includes
    something it does not, the day somebody reuses the key."""
    problems = []
    metrics = set(quota_metrics())
    for path in locale_files():
        labels = json.loads(path.read_text()).get("billing", {}).get("quota", {})
        for metric in labels:
            if metric not in metrics:
                problems.append(
                    f"{path.name}: label for `{metric}`, which no tier of the manifest sells"
                )
    return problems


def main():
    if not LOCALES_DIR.is_dir():
        print("FAIL  the module ships no locales/ directory")
        return 1

    problems = check_the_usage_metric_is_one_the_tiers_sell()
    problems += check_every_metric_is_named_in_every_language()
    problems += check_no_label_survives_its_metric()
    problems += check_non_english_labels_are_translated()

    for problem in problems:
        print(f"FAIL  {problem}")
    if problems:
        print(f"\n{len(problems)} quota label(s) missing or stale")
        return 1

    print(
        f"OK: {len(quota_metrics())} quota metric(s) named in "
        f"{len(locale_files())} language(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

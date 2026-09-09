#!/usr/bin/env python3
"""This module's paid levels are the COMMON ladder of ERPlora, and it sells none of them (#139).

WHAT A PERSON SAW. The plan tab of this module offered «WhatsApp Free · WhatsApp Starter · WhatsApp
Business · WhatsApp Flex», each with its own price and its own 15-day trial, while the assistant —
the other premium thing ERPlora sells — offered «Free · Basic · Pro · Enterprise». Two ladders for
two parts of the same product, plus a «Flex» level metered per message that belonged to neither. A
salon owner deciding how much to spend read two different vocabularies and a fourth level whose
bill she could not predict.

WHAT ADR-0474 DECIDED (2026-09-08, revised 2026-09-09). Every premium module that ERPlora writes
itself, and the assistant, use the SAME four levels — Gratis · Basic · Pro · Enterprise — and the
level is a RIGHT that travels with the hub's plan: it is not bought separately, there is no
per-module trial, and there is no metered level. Whoever runs out of their level moves up a plan.
So this manifest declares the ladder and its quotas, and declares no price of its own.

WHY THE QUOTAS ARE NAILED DOWN HERE. Under ADR-0474 the quota is the only lever left: the margin
rule is `Σ(quota × worst-case unit cost of the third party) ≤ 50 %` of the plan's net price, and
what makes it hold is that the quota BLOCKS when it runs out. Raising one of these numbers is
therefore a pricing decision that has to be taken with the measurement in hand, never a tweak in
passing — so raising one has to break this test and be argued in the pull request. The current
numbers are the ones ADR-0474 deploys with the planning cap (0,02 €/message); the target once the
assistant's real token cost is measured is 30 · 200 · 800 · 1200.

WHAT THIS TEST DOES NOT ASK FOR, AND WHY. `billing.tiers[].price` is REQUIRED by the shared
manifest schema (`schemas/module.schema.json`, mirrored in hub and module-toolkit) and by
`validate.mjs`, so the key cannot be dropped until ERPlora/module-toolkit#245 relaxes it. `0` is
the manifest's way of saying «nothing here is for sale», which is what ADR-0474 decided, so what
this test guards is that no tier carries a price ABOVE zero — the day the schema lets the key go,
this check keeps holding without a change.

Usage: tests/billing_common_ladder.contract.test.py   (exit 0 = green). No Postgres, no Docker.
"""

import json
import pathlib
import sys

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())
LOCALES_DIR = MODULE_DIR / "locales"

BILLING = MANIFEST.get("billing", {})
TIERS = BILLING.get("tiers", [])

#: ADR-0474 §4 — the same four levels in every premium module ERPlora writes itself, in this order.
COMMON_LADDER = ["free", "basic", "pro", "enterprise"]

#: ADR-0474, quota table «with the cap»: billable WhatsApp messages per month per level.
LADDER_QUOTAS = {"free": 30, "basic": 150, "pro": 500, "enterprise": 800}

#: The metric the quotas are counted in. Named here so a rename cannot slip the numbers past us.
QUOTA_METRIC = "billable_messages_per_month"

#: Source language of the strings (ADR-0055). The other catalogues are its translation.
SOURCE_LANGUAGE = "en"

#: The only level whose name is a WORD and not a brand: `Free` is `Gratis` to the person reading it.
#: `Basic`, `Pro` and `Enterprise` are the same in every language on purpose (ADR-0474 §4).
TRANSLATED_LEVEL = "free"


def locale_files():
    return sorted(LOCALES_DIR.glob("*.json"))


def check_the_ladder_is_the_common_one():
    """Exactly the four levels of ADR-0474, with those slugs and in that order. The slugs are an
    external contract (published manifest, `ModuleTier` in the SaaS, the `…/whatsapp/plan/` door),
    so this is the check that turns a rename into a migration instead of a typo."""
    slugs = [tier.get("slug") for tier in TIERS]
    if slugs == COMMON_LADDER:
        return []
    return [
        f"billing.tiers is {slugs} — ADR-0474 asks for exactly {COMMON_LADDER}: a level named "
        f"anything else reads as a different product from the assistant's, and one that is "
        f"missing leaves a plan with nothing to grant"
    ]


def check_no_level_is_metered():
    """ADR-0474 discards the metered level: a bill nobody can predict, in the ladder that is meant
    to be the simple part. `metered` and `overage_price` are the two keys that bring it back."""
    problems = []
    for tier in TIERS:
        slug = tier.get("slug")
        if tier.get("metered"):
            problems.append(
                f"billing.tiers[{slug}] is `metered` — ADR-0474 retired the measured level: the "
                f"quota blocks, it never overflows into a surcharge"
            )
        if tier.get("overage_price") is not None:
            problems.append(
                f"billing.tiers[{slug}] declares `overage_price` — there is no overage to charge "
                f"once the quota blocks"
            )
    return problems


def check_no_level_is_sold_on_its_own():
    """The level comes with the hub's plan (ADR-0474 §2): no price of its own and no trial of its
    own. A trial would also collide with the free level — a paid module ships a free tier OR 15
    days of trial, never both (module-toolkit#228)."""
    problems = []
    if BILLING.get("trial_days"):
        problems.append(
            f"billing.trial_days is {BILLING['trial_days']} — the level travels with the plan, so "
            f"there is nothing here to try out for free; it is also a second free ride on top of "
            f"the `free` level"
        )
    for tier in TIERS:
        slug = tier.get("slug")
        price = tier.get("price")
        if price:
            problems.append(
                f"billing.tiers[{slug}].price is {price} — no level of an ERPlora module is sold "
                f"separately any more: whoever runs out of theirs moves up a plan"
            )
        if tier.get("trial_days"):
            problems.append(
                f"billing.tiers[{slug}].trial_days is {tier['trial_days']} — a level included in "
                f"the plan has nothing to try out"
            )
    return problems


def check_the_quotas_are_the_ones_the_margin_rule_allows():
    """The quota is the only lever ADR-0474 leaves, and the margin rule is what sets it. Changing
    a number here changes what ERPlora pays Meta for a plan it already sold."""
    problems = []
    for tier in TIERS:
        slug = tier.get("slug")
        expected = LADDER_QUOTAS.get(slug)
        if expected is None:
            continue  # an unknown slug is already reported by the ladder check
        quota = tier.get("quota")
        if not isinstance(quota, dict) or QUOTA_METRIC not in quota:
            problems.append(
                f"billing.tiers[{slug}] sells no `{QUOTA_METRIC}` — a level with no cap is a bill "
                f"with no ceiling (ADR-0474 margin rule)"
            )
            continue
        if quota[QUOTA_METRIC] != expected:
            problems.append(
                f"billing.tiers[{slug}].quota.{QUOTA_METRIC} is {quota[QUOTA_METRIC]}, ADR-0474 "
                f"deploys {expected} — raising it needs the measurement in hand, not a tweak"
            )
    return problems


def check_every_level_is_named_in_every_language():
    """The plan tab paints the level's name. «Basic», «Pro» and «Enterprise» read the same in both
    languages by design — the ladder's name is common on purpose (ADR-0474 §4) — but «Free» is
    «Gratis» to the salon owner reading it, so the words ship here, next to the quota labels the
    module already translates (hub#1604). The hub paints them in hub#1686."""
    problems = []
    slugs = [tier.get("slug") for tier in TIERS if tier.get("slug")]
    for path in locale_files():
        names = json.loads(path.read_text()).get("billing", {}).get("tiers", {})
        for slug in slugs:
            label = names.get(slug)
            if label is None:
                problems.append(
                    f"{path.name}: no name for the level `{slug}` — the plan screen would read in "
                    f"English on a {path.stem} hub"
                )
            elif not str(label).strip():
                problems.append(
                    f"{path.name}: the name for the level `{slug}` is blank"
                )
        for slug in names:
            if slug not in slugs:
                problems.append(
                    f"{path.name}: name for the level `{slug}`, which the manifest no longer "
                    f"sells — a leftover that promises a level that is gone"
                )
    return problems


def check_the_one_level_that_is_a_word_is_translated():
    """`free` is the only rung whose name has to change language, and it is the rung the whole
    catalogue exists for: without it the plan tab already read `Free`, in English, off the manifest.
    Presence is not enough here — copying the English word into `es.json` leaves the screen exactly
    as broken as leaving the key out, and passes every other check in this file."""
    problems = []
    if TRANSLATED_LEVEL not in [tier.get("slug") for tier in TIERS]:
        return problems  # the ladder check already reports a manifest without it
    source = None
    for path in locale_files():
        if path.stem == SOURCE_LANGUAGE:
            source = json.loads(path.read_text()).get("billing", {}).get("tiers", {}).get(
                TRANSLATED_LEVEL
            )
    if source is None:
        return problems  # a missing source name is already reported above
    for path in locale_files():
        if path.stem == SOURCE_LANGUAGE:
            continue
        name = json.loads(path.read_text()).get("billing", {}).get("tiers", {}).get(
            TRANSLATED_LEVEL
        )
        if name is not None and str(name).strip() == str(source).strip():
            problems.append(
                f"{path.name}: the level `{TRANSLATED_LEVEL}` is still called `{source}` — the "
                f"same word as {SOURCE_LANGUAGE}.json, so nobody translated it and the plan screen "
                f"reads in English on a {path.stem} hub, which is what this catalogue exists to fix"
            )
    return problems


def main():
    if not LOCALES_DIR.is_dir():
        print("FAIL  the module ships no locales/ directory")
        return 1
    if BILLING.get("tier") != "premium":
        print(
            "FAIL  billing.tier is not `premium` — this module consumes a third party's API"
        )
        return 1

    problems = check_the_ladder_is_the_common_one()
    problems += check_no_level_is_metered()
    problems += check_no_level_is_sold_on_its_own()
    problems += check_the_quotas_are_the_ones_the_margin_rule_allows()
    problems += check_every_level_is_named_in_every_language()
    problems += check_the_one_level_that_is_a_word_is_translated()

    for problem in problems:
        print(f"FAIL  {problem}")
    if problems:
        print(f"\n{len(problems)} problem(s) with the common plan ladder (ADR-0474)")
        return 1

    print(
        f"OK: the common ladder {COMMON_LADDER} is declared, none of it is sold on its own, "
        f"and every level is named in {len(locale_files())} language(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

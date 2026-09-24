#!/usr/bin/env python3
"""Every permission a recipe asks for is explained in a sentence, in every language it ships (flows#114).

The Automations gallery shows the owner, before installing a recipe of this module, the list of
permissions it will ask for. Without a `reason` the card can only print the internal name
(`staff.schedules.list_for_member`), and the owner cannot tell what they are authorising. The
sentence travels in `<family>.grants.json` as `reason: { en, es }` beside each grant; the hub
serves it as it came and the gallery paints it in the owner's language.

The rule: every grant of every family carries a `reason` with EXACTLY the languages the family's
documents ship (`<family>.<lang>.flow.json`), each a non-empty sentence that is not the grant's own
internal name. The battery checks its own rule first (`self_check`), so a blinded rule cannot stay
green.

Usage: tests/grant_reasons.test.py   (exit 0 = green)
"""

import json
import pathlib
import sys

FLOWS_DIR = pathlib.Path(__file__).resolve().parent.parent / "flows"


def family_languages():
    """`family -> {lang}` from the documents the module ships."""
    out = {}
    for path in FLOWS_DIR.glob("*.flow.json"):
        family, lang = path.name.split(".")[:2]
        out.setdefault(family, set()).add(lang)
    return out


def problems_in(name, sidecar, languages):
    problems = []
    for index, grant in enumerate(sidecar.get("grants", []), start=1):
        at = f"{name}: grant {index} (`{grant.get('value')}`)"
        reason = grant.get("reason")
        if not isinstance(reason, dict):
            problems.append(f"{at} has no `reason` — the owner would read its internal name")
            continue
        if set(reason) != languages:
            problems.append(
                f"{at}: `reason` is in {sorted(reason)}, the recipe ships {sorted(languages)}"
            )
        for lang, sentence in reason.items():
            if not isinstance(sentence, str) or not sentence.strip():
                problems.append(f"{at}: `reason.{lang}` is not a sentence")
            elif sentence.strip() == grant.get("value"):
                problems.append(f"{at}: `reason.{lang}` repeats the internal name")
    return problems


def self_check():
    """The rule catches what it exists for; otherwise it is green by construction."""
    langs = {"en", "es"}
    good = {"kind": "query", "value": "customers.list", "reason": {"en": "Look up", "es": "Buscar"}}
    cases = {
        "no reason": {"kind": "query", "value": "customers.list"},
        "one language": {**good, "reason": {"en": "Look up"}},
        "empty sentence": {**good, "reason": {"en": "Look up", "es": " "}},
        "internal name": {**good, "reason": {"en": "customers.list", "es": "Buscar"}},
    }
    failures = []
    if problems_in("self", {"grants": [good]}, langs):
        failures.append("a well-explained grant is refused")
    for label, grant in cases.items():
        if not problems_in("self", {"grants": [grant]}, langs):
            failures.append(f"the rule is blind to: {label}")
    return failures


def main():
    blind = self_check()
    for b in blind:
        print(f"FAIL  self_check: {b}")
    if blind:
        return 1
    languages = family_languages()
    if not languages:
        print("FAIL  no recipe in flows/ — this battery proved nothing")
        return 1
    problems = []
    for family, langs in sorted(languages.items()):
        path = FLOWS_DIR / f"{family}.grants.json"
        problems += problems_in(path.name, json.loads(path.read_text()), langs)
    for p in problems:
        print(f"FAIL  {p}")
    if problems:
        return 1
    print(f"OK: every permission of {len(languages)} recipe(s) is explained in {sorted(set().union(*languages.values()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

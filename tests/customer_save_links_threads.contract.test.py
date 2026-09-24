#!/usr/bin/env python3
"""Saving a customer card claims the unlinked thread of her number (whatsapp_inbox#160).

Why this file exists. whatsapp_inbox#149 links a thread when a message comes in from a number that
is on file. Two threads stayed without a customer: the one of somebody who wrote BEFORE her card
existed (the bookings recipe does not create one), and every thread from before the module learnt
to link — both only got their customer at her NEXT message. The fix listens to the customers
module's own `customer.created` / `customer.updated` (their payload is the saved sheet, `phone`
included, plus `new_id` / `customer_id`) with a Tier-2 command that runs the same rule from the
card's side and lands through the same fill-only write as #149.

What is checked here, each one a way the chain breaks silently:

1. **Both events are wired** to the listener. The event names are the ones `customers` really
   declares in `events.emits` — the issue guessed `customers.customer.created`, which nobody emits,
   and a listener of a name nobody emits is green here and dead in production.
2. **The listener is closed and real**: `internal`, a permission, the WASM function it calls is
   EXPORTED by the handler.
3. **It pre-loads `customers.by_phone` for `payload.phone`** — unfiltered, the handler gets
   one page of the whole list and cannot tell a unique card from a twin on page two — and the read
   is not `required`, or a failing read would dead-letter the customer event.
4. **It lands through `_link_customer_threads_write`**, the fill-only door that finds the thread
   by NUMBER (whatsapp_inbox#162: a card typed without the country code is `600111222`, the
   thread is keyed `34600111222`); its behaviour is pinned against real Postgres in
   `customer_save_links_threads.pg.test.py`.

The decision (which card, twins, the fresh `new_id` of an edit) is pinned by the handler's Rust
tests (`handler/src/lib.rs`, `link_customer_threads_*`); the end-to-end chain on the real runtime by
`tests/e2e/known_customer_link_e2e.rs`.

Usage: tests/customer_save_links_threads.contract.test.py   (exit 0 = green)
"""

import json
import pathlib
import re
import sys

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text())
CUSTOMERS_MANIFEST = MODULE_DIR.parent / "customers" / "module.json"

EVENTS = ("customer.created", "customer.updated")
LISTENER = "whatsapp_inbox._link_customer_threads"
WRITE = "whatsapp_inbox._link_customer_threads_write"
FUNCTION = "link_customer_threads"
READ = "customers.by_phone"


def check():
    problems = []
    listen = (MANIFEST.get("events") or {}).get("listen") or {}
    for event in EVENTS:
        target = (listen.get(event) or {}).get("command")
        if target != LISTENER:
            problems.append(
                f"`{event}` is not routed to `{LISTENER}` (got {target!r}): a card saved after "
                "she wrote never claims her thread"
            )

    # The names must be the ones the customers module really emits. Only checkable when the
    # sibling checkout is there; it is not a pass when it is missing, it is said.
    if CUSTOMERS_MANIFEST.exists():
        emits = (json.loads(CUSTOMERS_MANIFEST.read_text()).get("events") or {}).get(
            "emits", []
        )
        for event in EVENTS:
            if event not in emits:
                problems.append(
                    f"`customers` does not emit `{event}`: the listener would never run"
                )
    else:
        print(
            f"SKIP: {CUSTOMERS_MANIFEST} is missing; the emitted event names were not checked"
        )

    spec = MANIFEST.get("commands", {}).get(LISTENER)
    if not spec:
        return problems + [f"`{LISTENER}` is not declared"]
    if spec.get("internal") is not True:
        problems.append(f"`{LISTENER}` must be `internal`: only the relay may run it")
    if not spec.get("permission"):
        problems.append(f"`{LISTENER}` declares no `permission`")
    if spec.get("sql"):
        problems.append(
            f"`{LISTENER}` must not carry its own SQL: it lands through `{WRITE}`"
        )

    handler = spec.get("handler") or {}
    if handler.get("type") != "wasm" or handler.get("function") != FUNCTION:
        problems.append(
            f"`{LISTENER}` must call the WASM function `{FUNCTION}`, got {handler!r}"
        )
    lib = (MODULE_DIR / "handler" / "src" / "lib.rs").read_text()
    if not re.search(r"#\[plugin_fn\]\s*pub fn " + FUNCTION + r"\(", lib):
        problems.append(
            f"the handler does not EXPORT `{FUNCTION}`: the listener would trap"
        )
    if not re.search(
        r'fn link_customer_threads_pure[\s\S]*?"' + re.escape(WRITE) + '"', lib
    ):
        problems.append(f"`{FUNCTION}` does not land through `{WRITE}`")

    reads = [
        r
        for r in spec.get("reads", [])
        if isinstance(r, dict) and r.get("query") == READ
    ]
    if not reads:
        problems.append(
            f"`{LISTENER}` does not pre-load `{READ}`: the handler knows no card"
        )
    elif (reads[0].get("params") or {}).get("phone") != "payload.phone":
        problems.append(
            f"`{LISTENER}` reads `{READ}` without `phone: payload.phone` "
            f"({reads[0].get('params')!r}): a twin card on page two would go unseen"
        )
    elif reads[0].get("required"):
        problems.append(
            f"`{LISTENER}` marks `{READ}` as required: a failing read would dead-letter the "
            "customer event instead of just not linking"
        )

    schema_rel = spec.get("schema")
    if not schema_rel:
        problems.append(f"`{LISTENER}` declares no `schema`")
    else:
        schema = json.loads((MODULE_DIR / schema_rel).read_text())
        if schema.get("required") or schema.get("additionalProperties") is False:
            problems.append(
                f"`{schema_rel}` is strict: the listener gets the customer event VERBATIM, and a "
                "stricter schema dead-letters it instead of linking nobody"
            )
    return problems


def main():
    problems = check()
    if problems:
        print("FAIL — saving a customer card does not claim the thread of her number:")
        for p in problems:
            print(f"  · {p}")
        return 1
    print(
        "OK — customer.created / customer.updated claim the unlinked thread of the saved number."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

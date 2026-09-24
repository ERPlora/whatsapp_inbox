//! whatsapp_inbox#149 — a message from a number that is on file links its conversation to that
//! customer with NO automation installed, end to end on the REAL runtime:
//!
//! ```text
//! core event hub.whatsapp.message_received          (as `inbound_poll.rs::event_payload` writes it)
//!         ↓ relay: `_ingest_inbound_message`        → conversation + message
//!         ↓ emits whatsapp_inbox.message.received
//!         ↓ relay: `_link_known_customer`           → WASM handler, `customers.by_phone` pre-loaded
//!         ↓ intent `_link_known_customer_write`     → conversation.customer_id
//! ```
//!
//! whatsapp_inbox#160 adds the other direction: `customer.created` / `customer.updated` →
//! `_link_customer_threads` → `_link_customer_threads_write`, for a thread that existed before the
//! card; whatsapp_inbox#162 makes both find a card typed without the country code (`600 111 222`).
//!
//! What only the runtime can prove, and the module's own tests cannot: that a module may listen to
//! its OWN event, that the `reads` of a listener are served (in scope through `depends_on`,
//! keyed by `payload.contact`), and that the handler's intent lands.
//!
//! Run with: `ERPLORA_MODULES_DIR=…/modules-workspace/modules DATABASE_URL=… cargo test -p
//! erplora-runtime --test known_customer_link_e2e` (see `README.md` next to this file).
use std::path::PathBuf;

use erplora_db::{testutil::fresh_db, Params};
use erplora_runtime::{outbox, RequestContext, Runtime};
use serde_json::{json, Value};

const HUB: &str = "hub-wa-known-customer-e2e";
const WA_ID: &str = "34600111222";

fn module(id: &str) -> PathBuf {
    PathBuf::from(
        std::env::var("ERPLORA_MODULES_DIR")
            .expect("ERPLORA_MODULES_DIR must point at modules-workspace/modules"),
    )
    .join(id)
}

fn owner() -> RequestContext {
    RequestContext::new(HUB, "owner", ["*".to_string()])
}

/// A hub with no automation at all: just the two modules, no flow.
async fn runtime() -> Runtime {
    let db = fresh_db().await;
    let mut rt = Runtime::with_hub_id(Box::new(db), HUB);
    rt.ensure_system_tables().await.unwrap();
    for id in ["customers", "whatsapp_inbox"] {
        rt.install_from_dir(&module(id))
            .await
            .unwrap_or_else(|e| panic!("installing `{id}`: {e}"));
    }
    rt
}

async fn rows(rt: &Runtime, sql: &str) -> Vec<Value> {
    rt.db_for_test().query(sql, &Params::new()).await.unwrap().rows
}

async fn customer_on_file(rt: &Runtime, name: &str, phone: &str) -> String {
    rt.execute_command("customers.create", &params(json!({ "name": name, "phone": phone })), &owner())
        .await
        .unwrap_or_else(|e| panic!("creating `{name}`: {e}"));
    let found = rows(rt, &format!("SELECT id FROM customers_customer WHERE name = '{name}'")).await;
    found[0]["id"].as_str().unwrap().to_string()
}

fn params(v: Value) -> Params {
    v.as_object().unwrap().clone().into_iter().collect()
}

/// Exactly the keys `crates/server/src/inbound_poll.rs::event_payload` writes for a customer's
/// message (hub#1612: `contact` is the other end, `direction` who spoke).
async fn a_customer_writes(rt: &Runtime, wa_message_id: &str) {
    let payload = params(json!({
        "wa_message_id": wa_message_id,
        "from": WA_ID,
        "direction": "inbound",
        "contact": WA_ID,
        "source": "live",
        "text": "hola",
        "received_at": "2026-09-24T09:00:00+00:00",
        "message": { "id": wa_message_id, "from": WA_ID, "type": "text", "text": { "body": "hola" } },
    }));
    assert!(outbox::insert_core_event_once(
        rt.db_for_test(),
        &format!("wa-{wa_message_id}"),
        HUB,
        "hub.whatsapp.message_received",
        &payload,
    )
    .await
    .unwrap());
    rt.drain_outbox().await.unwrap();
}

async fn thread_customer(rt: &Runtime) -> Value {
    let convs = rows(rt, "SELECT customer_id FROM whatsapp_inbox_conversation").await;
    assert_eq!(convs.len(), 1, "one contact, one thread");
    convs[0]["customer_id"].clone()
}

async fn nothing_dead_lettered(rt: &Runtime) {
    let dead = rt.list_dead_events(10).await.unwrap();
    assert!(dead.is_empty(), "the listener must never give up on a message: {dead:?}");
}

#[tokio::test]
async fn a_message_from_a_number_on_file_links_the_thread_with_no_automation() {
    let rt = runtime().await;
    // Somebody else first, so a handler that took «the first row» of an unfiltered read is caught.
    customer_on_file(&rt, "Eva", "+34600999888").await;
    let ana = customer_on_file(&rt, "Ana", "+34600111222").await;

    a_customer_writes(&rt, "wamid.KNOWN").await;

    assert_eq!(thread_customer(&rt).await, json!(ana), "the inbox knows the thread is Ana's");
    nothing_dead_lettered(&rt).await;
}

#[tokio::test]
async fn a_number_nobody_has_on_file_links_nobody_and_the_message_still_lands() {
    let rt = runtime().await;
    customer_on_file(&rt, "Eva", "+34600999888").await;

    a_customer_writes(&rt, "wamid.STRANGER").await;

    assert_eq!(thread_customer(&rt).await, Value::Null);
    let msgs = rows(&rt, "SELECT body FROM whatsapp_inbox_message").await;
    assert_eq!(msgs.len(), 1, "the message itself is ingested either way");
    nothing_dead_lettered(&rt).await;
}

#[tokio::test]
async fn a_link_somebody_already_made_is_not_overwritten_by_the_phone_match() {
    let rt = runtime().await;
    let ana = customer_on_file(&rt, "Ana", "+34600111222").await;
    let eva = customer_on_file(&rt, "Eva", "+34600999888").await;

    a_customer_writes(&rt, "wamid.FIRST").await;
    assert_eq!(thread_customer(&rt).await, json!(ana));

    // The owner knows better (the phone is the family's): she files the thread under Eva by hand.
    rt.execute_command(
        "whatsapp_inbox.conversations.link_customer",
        &params(json!({ "wa_contact_id": WA_ID, "customer_id": eva })),
        &owner(),
    )
    .await
    .unwrap();

    a_customer_writes(&rt, "wamid.SECOND").await;
    assert_eq!(thread_customer(&rt).await, json!(eva), "the person's link wins over the match");
    nothing_dead_lettered(&rt).await;
}

// ── whatsapp_inbox#160: the card saved AFTER she wrote claims her thread ──────────────────────────

#[tokio::test]
async fn a_customer_filed_after_she_wrote_gets_her_thread_without_a_new_message() {
    let rt = runtime().await;
    a_customer_writes(&rt, "wamid.BEFORE-CARD").await;
    assert_eq!(thread_customer(&rt).await, Value::Null, "nobody is on file yet");

    // The owner files her afterwards; the thread must not wait for her next message.
    let ana = customer_on_file(&rt, "Ana", "+34 600 111 222").await;
    rt.drain_outbox().await.unwrap();

    assert_eq!(thread_customer(&rt).await, json!(ana), "saving the card claimed the thread");
    nothing_dead_lettered(&rt).await;
}

#[tokio::test]
async fn fixing_the_phone_on_a_card_claims_the_thread_of_the_right_number() {
    let rt = runtime().await;
    let ana = customer_on_file(&rt, "Ana", "+34600000000").await;
    a_customer_writes(&rt, "wamid.WRONG-PHONE").await;
    assert_eq!(thread_customer(&rt).await, Value::Null, "the card had a wrong number");

    rt.execute_command(
        "customers.update",
        &params(json!({
            "customer_id": ana, "name": "Ana", "email": "", "phone": "+34600111222", "tax_id": "",
            "address": "", "city": "", "postal_code": "", "country": "", "notes": "",
            "lifecycle_stage": "lead", "source": "walk_in", "company_name": "", "birthday": null,
            "anniversary": null, "preferred_channel": "none", "is_active": 1,
        })),
        &owner(),
    )
    .await
    .unwrap();
    rt.drain_outbox().await.unwrap();

    assert_eq!(thread_customer(&rt).await, json!(ana), "the corrected card claimed the thread");
    nothing_dead_lettered(&rt).await;
}

#[tokio::test]
async fn two_cards_with_the_same_number_leave_the_thread_for_a_human() {
    let rt = runtime().await;
    a_customer_writes(&rt, "wamid.SHARED").await;
    customer_on_file(&rt, "Ana", "+34600111222").await;
    customer_on_file(&rt, "Eva", "+34600111222").await;
    rt.drain_outbox().await.unwrap();

    // Both cards exist by the time the relay runs either event: each one sees its twin, so the
    // shared number is left for a human — the same rule as a message from that number.
    assert_eq!(thread_customer(&rt).await, Value::Null, "a shared number links nobody");
    nothing_dead_lettered(&rt).await;
}

// ── whatsapp_inbox#162: the card typed the way people type it in Spain ─────────────────────────────

#[tokio::test]
async fn a_card_typed_without_the_country_code_is_recognised_when_she_writes() {
    let rt = runtime().await;
    customer_on_file(&rt, "Eva", "611 222 333").await;
    let ana = customer_on_file(&rt, "Ana", "600 111 222").await;

    a_customer_writes(&rt, "wamid.NATIONAL-CARD").await;

    assert_eq!(thread_customer(&rt).await, json!(ana), "600 111 222 is 34600111222");
    nothing_dead_lettered(&rt).await;
}

#[tokio::test]
async fn a_card_typed_without_the_country_code_claims_the_thread_she_opened_before() {
    let rt = runtime().await;
    a_customer_writes(&rt, "wamid.BEFORE-NATIONAL-CARD").await;
    assert_eq!(thread_customer(&rt).await, Value::Null, "nobody is on file yet");

    let ana = customer_on_file(&rt, "Ana", "600 111 222").await;
    rt.drain_outbox().await.unwrap();

    assert_eq!(thread_customer(&rt).await, json!(ana), "the national card claimed 34600111222");
    nothing_dead_lettered(&rt).await;
}

#[tokio::test]
async fn a_national_card_and_an_international_twin_leave_the_thread_for_a_human() {
    let rt = runtime().await;
    customer_on_file(&rt, "Ana", "600 111 222").await;
    customer_on_file(&rt, "Eva", "+34 600-111-222").await;

    a_customer_writes(&rt, "wamid.TWINS-TYPED-APART").await;

    assert_eq!(thread_customer(&rt).await, Value::Null, "two cards, one number: nobody");
    nothing_dead_lettered(&rt).await;
}

// ── whatsapp_inbox#163: the threads from before the automatic link, swept once ────────────────────

/// A thread as an older version of the module left it: written before the link existed, so it has
/// no customer and the sweep has never seen it. Nothing emits an event for it — that is the bug.
async fn a_thread_from_before_the_update(rt: &Runtime, id: &str, wa_contact_id: &str) {
    rt.db_for_test()
        .execute(
            &format!(
                "INSERT INTO whatsapp_inbox_conversation (id, hub_id, wa_contact_id, contact_name, \
                 contact_phone, created_at) VALUES ('{id}', '{HUB}', '{wa_contact_id}', 'x', \
                 '+{wa_contact_id}', '2026-01-01T09:00:00+00:00')"
            ),
            &Params::new(),
        )
        .await
        .unwrap();
}

/// The module's scheduled sweep, run the way the relay loop runs it once its cron is due.
async fn the_sweep_runs(rt: &Runtime) -> usize {
    rt.db_for_test()
        .execute(
            "UPDATE _scheduled_tasks SET next_run = '2000-01-01T00:00:00+00:00' \
             WHERE module_id = 'whatsapp_inbox' AND name = 'sweep_unlinked_threads'",
            &Params::new(),
        )
        .await
        .unwrap();
    let ran = rt.process_scheduler(HUB).await.unwrap();
    rt.drain_outbox().await.unwrap();
    ran
}

async fn customer_of(rt: &Runtime, id: &str) -> Value {
    rows(rt, &format!("SELECT customer_id FROM whatsapp_inbox_conversation WHERE id = '{id}'")).await[0]
        ["customer_id"]
        .clone()
}

#[tokio::test]
async fn an_old_thread_is_linked_by_the_sweep_without_her_writing_or_her_card_being_saved() {
    let rt = runtime().await;
    customer_on_file(&rt, "Eva", "+34600999888").await;
    let ana = customer_on_file(&rt, "Ana", "600 111 222").await;
    rt.drain_outbox().await.unwrap(); // her card was saved long ago: nothing to claim back then
    a_thread_from_before_the_update(&rt, "t-old", WA_ID).await;
    a_thread_from_before_the_update(&rt, "t-stranger", "34611000000").await;

    assert_eq!(the_sweep_runs(&rt).await, 1, "the module's sweep is scheduled and due");

    assert_eq!(customer_of(&rt, "t-old").await, json!(ana), "the sweep linked the old thread");
    assert_eq!(customer_of(&rt, "t-stranger").await, Value::Null, "nobody on file: nobody linked");
    nothing_dead_lettered(&rt).await;
}

#[tokio::test]
async fn the_sweep_asks_once_and_never_overrides_a_link_or_picks_between_twins() {
    let rt = runtime().await;
    let eva = customer_on_file(&rt, "Eva", "+34600999888").await;
    customer_on_file(&rt, "Ana", "+34600111222").await;
    customer_on_file(&rt, "Ana bis", "600 111 222").await;
    rt.drain_outbox().await.unwrap();
    a_thread_from_before_the_update(&rt, "t-twins", WA_ID).await;
    a_thread_from_before_the_update(&rt, "t-by-hand", "34600555444").await;
    rt.db_for_test()
        .execute(&format!("UPDATE whatsapp_inbox_conversation SET customer_id = '{eva}' WHERE id = 't-by-hand'"), &Params::new())
        .await
        .unwrap();

    the_sweep_runs(&rt).await;
    assert_eq!(customer_of(&rt, "t-twins").await, Value::Null, "two cards, one number: a human decides");
    assert_eq!(customer_of(&rt, "t-by-hand").await, json!(eva), "a link somebody made is kept");

    let swept = rows(&rt, "SELECT id FROM whatsapp_inbox_conversation WHERE link_swept_at IS NOT NULL").await;
    assert_eq!(swept.len(), 1, "only the unlinked thread was asked about: {swept:?}");
    let asked = rows(&rt, "SELECT id FROM _event_outbox WHERE event_name = 'whatsapp_inbox.conversation.link_pending'").await;
    the_sweep_runs(&rt).await;
    let asked_again = rows(&rt, "SELECT id FROM _event_outbox WHERE event_name = 'whatsapp_inbox.conversation.link_pending'").await;
    assert_eq!(asked.len(), 1, "one lookup for the one unlinked thread");
    assert_eq!(asked_again.len(), asked.len(), "a swept thread is not asked about again");
    nothing_dead_lettered(&rt).await;
}

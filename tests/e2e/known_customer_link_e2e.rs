//! whatsapp_inbox#149 — a message from a number that is on file links its conversation to that
//! customer with NO automation installed, end to end on the REAL runtime:
//!
//! ```text
//! core event hub.whatsapp.message_received          (as `inbound_poll.rs::event_payload` writes it)
//!         ↓ relay: `_ingest_inbound_message`        → conversation + message
//!         ↓ emits whatsapp_inbox.message.received
//!         ↓ relay: `_link_known_customer`           → WASM handler, `customers.list` pre-loaded
//!         ↓ intent `_link_known_customer_write`     → conversation.customer_id
//! ```
//!
//! What only the runtime can prove, and the module's own tests cannot: that a module may listen to
//! its OWN event, that the `reads` of a listener are served (in scope through `depends_on`,
//! filtered by `payload.contact` through the list engine), and that the handler's intent lands.
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

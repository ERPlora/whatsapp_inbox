//! whatsapp_inbox#262 — erasing a customer's data (GDPR art. 17) erases her WhatsApp threads too,
//! end to end on the REAL runtime:
//!
//! ```text
//! customers.anonymize {customer_id, reason}          (the «Erase data» of the customer sheet)
//!         ↓ emits customer.anonymized
//!         ↓ relay: `_on_customer_anonymized`         → her threads and messages lose every
//!                                                      personal datum and leave the inbox
//! ```
//!
//! The retired «Requests» tray's set-aside table goes too (whatsapp_inbox#264): installing this
//! module on a hub WITHOUT hub#2461 is refused (`foreign_table_write`), so this file also proves the
//! hub accepts the module's row writes on its own `_deprecated_*` table.
//!
//! The SQL is pinned row by row, tenancy and idempotence included, on a real Postgres in
//! `tests/customer_erasure.pg.test.py`. What only the runtime can prove: that the event reaches
//! this module with the payload the SQL binds (`customer_id`), that the internal listener is allowed
//! to run, and that the whole chain leaves nothing dead-lettered.
//!
//! Run with: `ERPLORA_MODULES_DIR=…/modules-workspace/modules DATABASE_URL=… cargo test -p
//! erplora-runtime --test customer_erasure_e2e` (see `README.md` next to this file).
use std::path::PathBuf;

use erplora_db::{testutil::fresh_db, Params};
use erplora_runtime::{outbox, RequestContext, Runtime};
use serde_json::{json, Value};

const HUB: &str = "hub-wa-customer-erasure-e2e";
const ANA: &str = "34600111222";
const EVA: &str = "34600999888";

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

fn params(v: Value) -> Params {
    v.as_object().unwrap().clone().into_iter().collect()
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

/// Exactly the keys `crates/server/src/inbound_poll.rs::event_payload` writes for a customer's message.
async fn writes(rt: &Runtime, wa_id: &str, wa_message_id: &str, text: &str) {
    let payload = params(json!({
        "wa_message_id": wa_message_id,
        "from": wa_id,
        "direction": "inbound",
        "contact": wa_id,
        "source": "live",
        "text": text,
        "received_at": "2026-10-04T09:00:00+00:00",
        "message": { "id": wa_message_id, "from": wa_id, "type": "text", "text": { "body": text } },
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

/// Every column of every thread and message of the inbox, as one text — what a DB reader sees.
async fn everything_stored(rt: &Runtime) -> String {
    rows(
        rt,
        "SELECT row_to_json(c)::text AS r FROM whatsapp_inbox_conversation c \
         UNION ALL SELECT row_to_json(m)::text FROM whatsapp_inbox_message m \
         UNION ALL SELECT row_to_json(q)::text FROM _deprecated_whatsapp_inbox_request q",
    )
    .await
    .iter()
    .map(|r| r["r"].as_str().unwrap().to_string())
    .collect::<Vec<_>>()
    .join("|")
}

/// A request the retired «Requests» tray extracted from `wa_id`'s thread, inserted raw: no command
/// writes that table any more (whatsapp_inbox#206), migration 013 only set it aside — and what it
/// kept is still that person's data (whatsapp_inbox#264).
async fn the_retired_tray_kept(rt: &Runtime, wa_id: &str, said: &str) {
    rt.db_for_test()
        .execute_batch(&format!(
            "INSERT INTO _deprecated_whatsapp_inbox_request (id, hub_id, conversation_id, \
             reference_number, data, raw_summary, notes, created_at) \
             SELECT 'req-' || c.id, c.hub_id, c.id, 'REQ-' || c.id, \
                    '{{\"phone\": \"+{wa_id}\"}}', '{said}', 'call back on {wa_id}', \
                    '2026-09-01T00:00:00+00:00' \
               FROM whatsapp_inbox_conversation c \
              WHERE c.hub_id = '{HUB}' AND c.wa_contact_id = '{wa_id}'"
        ))
        .await
        .unwrap();
}

/// The `wa_contact_id`s the inbox screen lists.
async fn inbox(rt: &Runtime) -> Vec<String> {
    let page = rt
        .execute_query_page("whatsapp_inbox.conversations.list", &Params::new(), &owner())
        .await
        .unwrap();
    page.rows.iter().map(|r| r["wa_contact_id"].as_str().unwrap().to_string()).collect()
}

async fn nothing_dead_lettered(rt: &Runtime) {
    let dead = rt.list_dead_events(10).await.unwrap();
    assert!(dead.is_empty(), "the erasure must never be given up on: {dead:?}");
}

/// Ana and Eva are on file and both wrote; their threads are linked to their sheets.
async fn two_customers_who_wrote(rt: &Runtime) -> (String, String) {
    let ana = customer_on_file(rt, "Ana Vidal", "+34600111222").await;
    let eva = customer_on_file(rt, "Eva Ruiz", "+34600999888").await;
    writes(rt, ANA, "wamid.ANA-1", "ana writes her new address").await;
    writes(rt, EVA, "wamid.EVA-1", "eva asks for a booking").await;
    let linked = rows(rt, "SELECT customer_id FROM whatsapp_inbox_conversation ORDER BY wa_contact_id").await;
    assert_eq!(
        linked.iter().map(|r| r["customer_id"].clone()).collect::<Vec<_>>(),
        vec![json!(ana), json!(eva)],
        "control: both threads must be linked first, or this test proves nothing"
    );
    (ana, eva)
}

#[tokio::test]
async fn erasing_a_customer_erases_her_whatsapp_threads_and_nobody_elses() {
    let rt = runtime().await;
    let (ana, _eva) = two_customers_who_wrote(&rt).await;
    the_retired_tray_kept(&rt, ANA, "ana asked the tray for a colour").await;
    the_retired_tray_kept(&rt, EVA, "eva asked the tray for a table").await;
    let before = everything_stored(&rt).await;
    for pii in ["600111222", "ana writes her new address", "wamid.ANA-1", "ana asked the tray"] {
        assert!(before.contains(pii), "control: `{pii}` must be stored before the erasure");
    }

    rt.execute_command(
        "customers.anonymize",
        &params(json!({ "customer_id": ana, "reason": "GDPR request by email" })),
        &owner(),
    )
    .await
    .unwrap();
    rt.drain_outbox().await.unwrap();

    let after = everything_stored(&rt).await;
    for pii in ["600111222", "Ana Vidal", "ana writes her new address", "wamid.ANA-1", "ana asked the tray"] {
        assert!(!after.contains(pii), "`{pii}` is still stored after her erasure: {after}");
    }
    for kept in ["600999888", "eva asks for a booking", "wamid.EVA-1", "eva asked the tray"] {
        assert!(after.contains(kept), "Eva's `{kept}` went with Ana's erasure: {after}");
    }
    assert_eq!(inbox(&rt).await, vec![EVA.to_string()], "the inbox still lists Ana");
    nothing_dead_lettered(&rt).await;
}

#[tokio::test]
async fn if_she_writes_again_after_the_erasure_it_is_a_new_unlinked_thread() {
    let rt = runtime().await;
    let (ana, _eva) = two_customers_who_wrote(&rt).await;
    rt.execute_command("customers.anonymize", &params(json!({ "customer_id": ana })), &owner())
        .await
        .unwrap();
    rt.drain_outbox().await.unwrap();

    writes(&rt, ANA, "wamid.ANA-2", "hello again").await;

    let live = rows(
        &rt,
        &format!(
            "SELECT customer_id FROM whatsapp_inbox_conversation WHERE wa_contact_id = '{ANA}' AND is_deleted = 0"
        ),
    )
    .await;
    assert_eq!(live.len(), 1, "her new message must open a live thread: {live:?}");
    assert_eq!(live[0]["customer_id"], Value::Null, "the new thread is linked to the erased sheet");
    assert!(inbox(&rt).await.contains(&ANA.to_string()), "her new thread is not in the inbox");
    let erased_msgs = rows(
        &rt,
        "SELECT count(*) AS n FROM whatsapp_inbox_message m JOIN whatsapp_inbox_conversation c \
         ON c.id = m.conversation_id AND c.hub_id = m.hub_id WHERE c.is_deleted = 1 AND m.body <> ''",
    )
    .await;
    assert_eq!(erased_msgs[0]["n"], json!(0), "the new message landed in the erased thread");
    nothing_dead_lettered(&rt).await;
}

#[tokio::test]
async fn a_plain_delete_of_the_sheet_is_not_an_erasure() {
    // «Delete» on the customer list is a soft delete that keeps the sheet's own data; the GDPR
    // erasure is «Erase data» (`customers.anonymize`). The inbox mirrors that: deleting the sheet
    // does not wipe the conversation history (Shopify: deleting a customer ≠ `customers/redact`).
    let rt = runtime().await;
    let (ana, _eva) = two_customers_who_wrote(&rt).await;
    let before = everything_stored(&rt).await;

    rt.execute_command("customers.delete", &params(json!({ "customer_id": ana })), &owner())
        .await
        .unwrap();
    rt.drain_outbox().await.unwrap();

    assert_eq!(everything_stored(&rt).await, before, "a soft delete of the sheet erased her chats");
    nothing_dead_lettered(&rt).await;
}

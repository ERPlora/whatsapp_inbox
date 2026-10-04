//! whatsapp_inbox#263 — «Erase this number's data» erases one thread by hand, end to end on the
//! REAL runtime, for the person the erasure from the customer sheet (whatsapp_inbox#262) cannot
//! reach because she has no sheet:
//!
//! ```text
//! a message arrives (core event)  → thread + message, unlinked (no sheet)
//! whatsapp_inbox.conversations.erase {conversation_id}   → that thread and its messages lose every
//!                                                          personal datum and leave the inbox
//! ```
//!
//! The SQL is pinned row by row, tenancy and idempotence included, on a real Postgres in
//! `tests/number_erasure.pg.test.py`. What only the runtime can prove: that it installs the
//! command (schema, `expect_rows` anchored on a statement of its own), that the gates hold — only an
//! admin, never a blank id, an unknown thread refused with the declared CODE — and that the freed
//! number opens a new thread through the real ingest.
//!
//! Run with: `ERPLORA_MODULES_DIR=…/modules-workspace/modules DATABASE_URL=… cargo test -p
//! erplora-runtime --test number_erasure_e2e` (see `README.md` next to this file).
use std::path::PathBuf;

use erplora_db::{testutil::fresh_db, Params};
use erplora_runtime::{error_registry::error_code_of, outbox, RequestContext, Runtime};
use serde_json::{json, Value};

const HUB: &str = "hub-wa-number-erasure-e2e";
const PEPA: &str = "34600333444";
const EVA: &str = "34600999888";
const ERASE: &str = "whatsapp_inbox.conversations.erase";

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

/// What the manifest hands an employee: she reads the inbox, she does not erase it.
fn employee() -> RequestContext {
    RequestContext::new(HUB, "employee", ["whatsapp_inbox.view_conversation".to_string()])
}

async fn runtime() -> Runtime {
    let db = fresh_db().await;
    let mut rt = Runtime::with_hub_id(Box::new(db), HUB);
    rt.ensure_system_tables().await.unwrap();
    // `customers` too: the ingest asks it who wrote. Pepa is not on file, which is the point.
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

async fn thread_of(rt: &Runtime, wa_id: &str) -> String {
    let found = rows(
        rt,
        &format!("SELECT id, customer_id FROM whatsapp_inbox_conversation WHERE wa_contact_id = '{wa_id}'"),
    )
    .await;
    assert_eq!(found.len(), 1, "control: `{wa_id}` must have exactly one thread: {found:?}");
    found[0]["id"].as_str().unwrap().to_string()
}

/// Pepa (no sheet) and Eva both wrote.
async fn two_people_who_wrote(rt: &Runtime) -> String {
    writes(rt, PEPA, "wamid.PEPA-1", "pepa writes her new address").await;
    writes(rt, EVA, "wamid.EVA-1", "eva asks for a booking").await;
    let pepa = thread_of(rt, PEPA).await;
    let linked = rows(rt, &format!("SELECT customer_id FROM whatsapp_inbox_conversation WHERE id = '{pepa}'")).await;
    assert_eq!(linked[0]["customer_id"], Value::Null, "control: Pepa has no sheet to erase from");
    pepa
}

#[tokio::test]
async fn an_admin_erases_the_thread_of_somebody_with_no_sheet_and_nobody_elses() {
    let rt = runtime().await;
    let pepa = two_people_who_wrote(&rt).await;
    the_retired_tray_kept(&rt, PEPA, "pepa asked the tray for a table").await;
    the_retired_tray_kept(&rt, EVA, "eva asked the tray for a colour").await;
    let before = everything_stored(&rt).await;
    for pii in ["600333444", "pepa writes her new address", "wamid.PEPA-1", "pepa asked the tray"] {
        assert!(before.contains(pii), "control: `{pii}` must be stored before the erasure");
    }

    rt.execute_command(ERASE, &params(json!({ "conversation_id": pepa })), &owner())
        .await
        .unwrap();

    let after = everything_stored(&rt).await;
    for pii in ["600333444", "pepa writes her new address", "wamid.PEPA-1", "pepa asked the tray"] {
        assert!(!after.contains(pii), "`{pii}` is still stored after erasing her number: {after}");
    }
    for kept in ["600999888", "eva asks for a booking", "wamid.EVA-1", "eva asked the tray"] {
        assert!(after.contains(kept), "Eva's `{kept}` went with Pepa's erasure: {after}");
    }
    assert_eq!(inbox(&rt).await, vec![EVA.to_string()], "the inbox still lists Pepa");

    // Pressing it twice (a double tap, a retry) answers ok and erases nothing more.
    rt.execute_command(ERASE, &params(json!({ "conversation_id": pepa })), &owner())
        .await
        .expect("a second press must not be refused as «not found»");
    assert_eq!(everything_stored(&rt).await.contains("600999888"), true);
    assert!(rt.list_dead_events(10).await.unwrap().is_empty());
}

#[tokio::test]
async fn the_gates_hold_admin_only_never_blank_and_an_unknown_thread_is_refused_by_code() {
    let rt = runtime().await;
    let pepa = two_people_who_wrote(&rt).await;
    let before = everything_stored(&rt).await;

    let err = rt
        .execute_command(ERASE, &params(json!({ "conversation_id": pepa })), &employee())
        .await
        .expect_err("an employee must not erase a conversation");
    assert_eq!(error_code_of(&err), "permission_denied", "{err:?}");

    let err = rt
        .execute_command(ERASE, &params(json!({ "conversation_id": "" })), &owner())
        .await
        .expect_err("a blank id must be refused before any SQL runs");
    assert_eq!(error_code_of(&err), "invalid_payload", "{err:?}");

    let err = rt
        .execute_command(ERASE, &params(json!({ "conversation_id": "no-such-thread" })), &owner())
        .await
        .expect_err("an unknown thread must not answer ok");
    assert_eq!(error_code_of(&err), "whatsapp_inbox.conversation_not_found", "{err:?}");

    assert_eq!(everything_stored(&rt).await, before, "a refused erasure changed something");
}

#[tokio::test]
async fn if_she_writes_again_after_the_erasure_it_is_a_new_thread() {
    let rt = runtime().await;
    let pepa = two_people_who_wrote(&rt).await;
    rt.execute_command(ERASE, &params(json!({ "conversation_id": pepa })), &owner())
        .await
        .unwrap();

    writes(&rt, PEPA, "wamid.PEPA-2", "hello again").await;

    let fresh = thread_of(&rt, PEPA).await;
    assert_ne!(fresh, pepa, "her new message landed in the erased thread");
    assert!(inbox(&rt).await.contains(&PEPA.to_string()), "her new thread is not in the inbox");
    assert!(rt.list_dead_events(10).await.unwrap().is_empty());
}

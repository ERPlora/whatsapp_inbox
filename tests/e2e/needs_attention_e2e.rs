//! **A customer the automation could not answer stands out in the inbox until somebody of the
//! business answers her** (whatsapp_inbox#238).
//!
//! ```text
//!  she writes                          →  hub.whatsapp.message_received → conversation + message
//!  the recipe's assistant FAILS        →  «sorry, someone from the team will answer you»
//!    (or answers with nothing)         →  whatsapp_inbox.conversations.needs_attention
//!                                      →  the inbox list serves her FIRST with `needs_attention_at`
//!  the owner answers from the phone    →  the live echo (outbound) → the mark goes away
//! ```
//!
//! The pieces are pinned one by one elsewhere — the SQL on a real Postgres in
//! `tests/needs_attention.pg.test.py`, the recipes in `tests/flow_templates.test.py`
//! (`handoff_mark_problems`), the screen in `ui/…/erp-whatsapp-inbox-inbox.test.ts`. What only the
//! real runtime can say is that they hold TOGETHER: the recipe that ships is allowed to call the
//! door (its grants), the step lands on HER thread through `input.from`, the list the screen reads
//! puts her on top by default, and the echo the hub delivers for the owner's reply clears it.
//!
//! Run with: `ERPLORA_MODULES_DIR=…/modules-workspace/modules DATABASE_URL=… cargo test -p
//! erplora-runtime --test needs_attention_e2e` (see `README.md` next to this file).
use std::path::PathBuf;

use erplora_db::{testutil::fresh_db, Params};
use erplora_runtime::flows::executor::IoResult;
use erplora_runtime::{outbox, RequestContext, Runtime};
use serde_json::{json, Value};

const HUB: &str = "hub-wa-needs-attention-e2e";
const MODULE: &str = "whatsapp_inbox";
const FAMILY: &str = "appointment-from-whatsapp";
const OWNER: &str = "hub_user:owner";
const SHOP: &str = "34911000000";
const MARTA: &str = "34600111222";
const LUCIA: &str = "34600555666";

fn modules_dir() -> PathBuf {
    PathBuf::from(
        std::env::var("ERPLORA_MODULES_DIR")
            .expect("ERPLORA_MODULES_DIR must point at modules-workspace/modules"),
    )
}

fn owner() -> RequestContext {
    RequestContext::new(HUB, "owner", ["*".to_string()])
}

/// A salon with the booking neighbours, this module, and the WhatsApp reply turned on through this
/// module's own door — what «Activar» on the WhatsApp screen does.
async fn salon() -> Runtime {
    let mut rt = Runtime::with_hub_id(Box::new(fresh_db().await), HUB);
    rt.ensure_system_tables().await.unwrap();
    for id in ["customers", "taxes", "services", "staff", "schedules", "appointments", MODULE] {
        rt.install_from_dir(&modules_dir().join(id))
            .await
            .unwrap_or_else(|e| panic!("installing {id}: {e}"));
    }
    rt.activate_flow_template(MODULE, FAMILY, OWNER).await.unwrap();
    rt
}

/// How the assistant that looks at the diary answers this turn.
#[derive(Clone, Copy)]
enum Assistant {
    Fails,
    SaysNothing,
    Answers,
}

/// One message delivered by the hub like the SaaS relay does, drained through the listener.
async fn deliver(rt: &Runtime, wamid: &str, from: &str, contact: &str, direction: &str, at: &str) {
    let mut payload = Params::new();
    for (k, v) in [
        ("wa_message_id", json!(wamid)),
        ("from", json!(from)),
        ("contact", json!(contact)),
        ("direction", json!(direction)),
        ("source", json!("live")),
        ("text", json!("hola, quiero cita")),
        ("received_at", json!(at)),
    ] {
        payload.insert(k.into(), v);
    }
    let id = format!("wa-{wamid}");
    assert!(outbox::insert_core_event_once(rt.db_for_test(), &id, HUB, "hub.whatsapp.message_received", &payload)
        .await
        .unwrap());
    rt.drain_outbox().await.unwrap();
}

/// She writes and the recipe runs to its end, the booking assistant answering as `assistant`.
async fn she_writes(rt: &Runtime, wamid: &str, contact: &str, at: &str, assistant: Assistant) {
    deliver(rt, wamid, contact, contact, "inbound", at).await;
    for _ in 0..30 {
        let report = rt.process_flows().await.unwrap();
        for io in report.pending_io {
            let answer = match (io.step_id(), assistant) {
                ("know_the_customer", _) => IoResult::Done(json!({ "text": "card ok" })),
                (_, Assistant::Fails) => IoResult::Failed("llm_unavailable".into()),
                (_, Assistant::SaysNothing) => IoResult::Done(json!({ "text": "", "tool_calls": [], "slots": [] })),
                (_, Assistant::Answers) => IoResult::Done(json!({ "text": "Te apunto el martes a las 10", "tool_calls": [], "slots": [] })),
            };
            rt.complete_flow_io(io.run_id(), io.step_id(), answer).await.unwrap();
        }
    }
}

/// The owner answers her from the WhatsApp Business app: the hub delivers the ECHO (hub#1612).
async fn the_owner_answers(rt: &Runtime, wamid: &str, contact: &str, at: &str) {
    deliver(rt, wamid, SHOP, contact, "outbound", at).await;
    rt.process_flows().await.unwrap();
}

/// `(wa_contact_id, needs_attention_at)` of the inbox list, in the order the screen gets it when it
/// asks for nothing in particular — the manifest's default sort.
async fn inbox(rt: &Runtime) -> Vec<(String, Value)> {
    let page = rt
        .execute_query_page("whatsapp_inbox.conversations.list", &Params::new(), &owner())
        .await
        .unwrap();
    page.rows
        .iter()
        .map(|r| (r["wa_contact_id"].as_str().unwrap().to_string(), r["needs_attention_at"].clone()))
        .collect()
}

fn flagged(rows: &[(String, Value)], contact: &str) -> bool {
    rows.iter().any(|(c, at)| c == contact && at.is_string())
}

#[tokio::test]
async fn when_the_assistant_fails_her_thread_is_flagged_and_served_first() {
    let rt = salon().await;
    she_writes(&rt, "wamid.W238a", MARTA, "2026-09-28T09:00:00+00:00", Assistant::Fails).await;
    she_writes(&rt, "wamid.W238b", LUCIA, "2026-09-28T09:30:00+00:00", Assistant::Answers).await;

    let rows = inbox(&rt).await;
    assert!(flagged(&rows, MARTA), "the automation told her someone would answer and nothing remembers it: {rows:?}");
    assert!(!flagged(&rows, LUCIA), "a customer the automation DID answer is flagged too: {rows:?}");
    assert_eq!(
        rows.first().map(|(c, _)| c.as_str()),
        Some(MARTA),
        "the newer, answered thread still leads the inbox and buries the one waiting: {rows:?}"
    );
}

#[tokio::test]
async fn when_the_assistant_answers_with_nothing_her_thread_is_flagged_too() {
    let rt = salon().await;
    she_writes(&rt, "wamid.W238c", MARTA, "2026-09-28T09:00:00+00:00", Assistant::SaysNothing).await;
    let rows = inbox(&rt).await;
    assert!(flagged(&rows, MARTA), "a silent assistant left her with the apology and no mark: {rows:?}");
}

#[tokio::test]
async fn the_mark_goes_away_when_the_owner_answers_her_and_only_then() {
    let rt = salon().await;
    she_writes(&rt, "wamid.W238d", MARTA, "2026-09-28T09:00:00+00:00", Assistant::Fails).await;
    let since = inbox(&rt).await.into_iter().find(|(c, _)| c == MARTA).unwrap().1;
    assert!(since.is_string(), "the control did not flag her — this test stopped proving anything");

    // She writes again and the automation fails again: still waiting, and since the FIRST time.
    she_writes(&rt, "wamid.W238e", MARTA, "2026-09-28T09:10:00+00:00", Assistant::Fails).await;
    let again = inbox(&rt).await.into_iter().find(|(c, _)| c == MARTA).unwrap().1;
    assert_eq!(again, since, "her own next message or a second failure moved or cleared the mark");

    the_owner_answers(&rt, "wamid.W238f", MARTA, "2026-09-28T09:20:00+00:00").await;
    let rows = inbox(&rt).await;
    assert!(!flagged(&rows, MARTA), "the owner answered her from the phone and the mark is still up: {rows:?}");
}

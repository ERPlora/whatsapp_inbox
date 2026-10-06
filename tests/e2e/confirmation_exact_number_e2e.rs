//! **The «Confirmed!» WhatsApp reaches the conversation of THAT number, or nobody**
//! (whatsapp_inbox#279), run by the hub's real runtime.
//!
//! ```text
//!  the salon taps «Confirm»  →  appointments.appointments.confirm  →  appointments.appointment.confirmed
//!         ↓ the flow trigger of the SHIPPED recipe `appointment-confirmed-to-whatsapp`
//!  read the appointment  →  has a phone?  →  conversations.by_phone  →  international?  →  thread?
//!         ↓
//!  `flow.reminder.due` queued for her exact number — or the run stops on the step that says why
//! ```
//!
//! The bug this pins: the recipe looked her conversation up through `conversations.list`, whose
//! `contact_phone` filter is «contains». An appointment holding `600111` — an old card the E.164 task
//! of Clientes could not rewrite, or a phone typed by hand in the diary — found `+34600111222`, and
//! the confirmation went to Marta, who had booked nothing.
//!
//! Not a fixture: the modules are the published ones from `ERPLORA_MODULES_DIR`, the recipe and its
//! grants are the files shipped in `whatsapp_inbox/flows/`.
//!
//! Run with: `ERPLORA_MODULES_DIR=…/modules-workspace/modules DATABASE_URL=… cargo test -p
//! erplora-runtime --test confirmation_exact_number_e2e`
use std::path::PathBuf;

use erplora_db::{testutil::fresh_db, Params};
use erplora_runtime::flows::grants::{GrantKind, GrantSpec};
use erplora_runtime::flows::{store, NewFlow};
use erplora_runtime::{RequestContext, Runtime};
use serde_json::{json, Value};

const HUB: &str = "hub-wa-confirmation-e2e";
const MARTA: &str = "+34600111222";

const SALON: &[&str] = &[
    "customers",
    "taxes",
    "services",
    "staff",
    "schedules",
    "appointments",
    "whatsapp_inbox",
];

fn module(id: &str) -> PathBuf {
    PathBuf::from(
        std::env::var("ERPLORA_MODULES_DIR")
            .expect("ERPLORA_MODULES_DIR must point at modules-workspace/modules"),
    )
    .join(id)
}

fn shipped(name: &str) -> Value {
    let path = module("whatsapp_inbox").join("flows").join(name);
    serde_json::from_str(&std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{path:?}: {e}")))
        .expect("the shipped file is JSON")
}

/// The sidecar's grants as the hub installs them, pins included (hub#1623/#1662).
fn shipped_grants() -> Vec<GrantSpec> {
    shipped("appointment-confirmed-to-whatsapp.grants.json")["grants"]
        .as_array()
        .unwrap()
        .iter()
        .map(|g| {
            let mut spec = GrantSpec::pair(
                GrantKind::parse(g["kind"].as_str().unwrap()).unwrap(),
                g["value"].as_str().unwrap(),
            );
            if let Some(pin) = g["payload"].as_object() {
                spec.payload = pin.clone().into_iter().collect();
            }
            spec
        })
        .collect()
}

fn owner() -> RequestContext {
    RequestContext::new(HUB, "owner", ["*".to_string()])
}

async fn exec(rt: &Runtime, sql: &str) {
    rt.db_for_test()
        .execute(sql, &Params::new())
        .await
        .unwrap_or_else(|e| panic!("{sql}: {e}"));
}

/// A salon with the recipe on, and Marta's WhatsApp conversation in its inbox.
async fn the_salon() -> (Runtime, String) {
    let db = fresh_db().await;
    let mut rt = Runtime::with_hub_id(Box::new(db), HUB);
    rt.ensure_system_tables().await.unwrap();
    for id in SALON {
        rt.install_from_dir(&module(id))
            .await
            .unwrap_or_else(|e| panic!("installing `{id}`: {e}"));
    }
    let flow_id = rt
        .create_flow(
            &NewFlow {
                name: "Cita confirmada → WhatsApp".into(),
                enabled: true,
                definition: shipped("appointment-confirmed-to-whatsapp.es.flow.json"),
            },
            "hub_user:owner",
        )
        .await
        .unwrap()
        .id;
    rt.replace_flow_grants(&flow_id, &shipped_grants(), "hub_user:owner")
        .await
        .unwrap();
    exec(
        &rt,
        &format!(
            "INSERT INTO whatsapp_inbox_conversation \
             (id, hub_id, wa_contact_id, contact_name, contact_phone, is_deleted, created_at, last_message_at) \
             VALUES ('conv-marta', '{HUB}', '34600111222', 'Marta', '{MARTA}', 0, \
                     '2026-10-06T08:00:00+00:00', '2026-10-06T08:00:00+00:00')"
        ),
    )
    .await;
    (rt, flow_id)
}

/// The salon books an appointment holding `phone` and confirms it from the diary.
async fn confirm_with_phone(rt: &Runtime, id: &str, phone: &str) {
    exec(
        rt,
        &format!(
            "INSERT INTO appointments_appointment \
             (id, hub_id, customer_name, customer_phone, service_name, start_datetime, end_datetime, \
              duration_minutes, status, created_at) \
             VALUES ('{id}', '{HUB}', 'Lucía', '{}', 'Corte', '2026-10-20T10:30:00+00:00', \
                     '2026-10-20T11:00:00+00:00', 30, 'pending', '2026-10-06T08:00:00+00:00')",
            phone.replace('\'', "''")
        ),
    )
    .await;
    let mut params = Params::new();
    params.insert("appointment_id".into(), json!(id));
    rt.execute_command("appointments.appointments.confirm", &params, &owner())
        .await
        .unwrap_or_else(|e| panic!("confirming `{id}`: {e}"));
}

/// Runs the flows until the confirmation's run ends, and hands back its steps.
async fn the_run(rt: &Runtime, flow_id: &str) -> (String, Vec<store::FlowRunStep>) {
    // The relay: the confirmation event reaches the flow trigger, which only inserts the run.
    rt.drain_outbox().await.unwrap();
    for _ in 0..30 {
        let report = rt.process_flows().await.unwrap();
        assert!(report.pending_io.is_empty(), "the recipe has no step that waits on the server");
        let runs = rt.list_flow_runs(flow_id, 10, None).await.unwrap();
        let ended = [store::STATUS_DONE, store::STATUS_FAILED, store::STATUS_CANCELLED];
        if let [run] = runs.as_slice() {
            if ended.contains(&run.status.as_str()) {
                return (run.status.clone(), rt.get_flow_run(&run.id).await.unwrap().1);
            }
        }
    }
    panic!("the confirmation never started exactly one run that finished");
}

/// Every WhatsApp the hub queued: `(to, text)`.
async fn sent(rt: &Runtime) -> Vec<(Value, Value)> {
    rt.db_for_test()
        .query(
            "SELECT payload FROM _event_outbox WHERE event_name = 'flow.reminder.due'",
            &Params::new(),
        )
        .await
        .unwrap()
        .rows
        .iter()
        .map(|r| {
            let p: Value = serde_json::from_str(r["payload"].as_str().unwrap()).unwrap();
            (p["to"].clone(), p["vars"]["text"].clone())
        })
        .collect()
}

/// The step the run stopped on: the last one it ran, a condition that did not match.
fn stopped_on(steps: &[store::FlowRunStep]) -> String {
    let last = steps.last().expect("the run ran at least one step");
    assert_eq!(
        last.output.get("matched"),
        Some(&json!(false)),
        "the run ended on a condition that did not match: {steps:?}"
    );
    last.step_id.clone()
}

#[tokio::test]
async fn her_exact_number_gets_the_confirmation() {
    let (rt, flow_id) = the_salon().await;
    confirm_with_phone(&rt, "apt-marta", MARTA).await;

    let (status, _) = the_run(&rt, &flow_id).await;
    assert_eq!(status, store::STATUS_DONE);
    let out = sent(&rt).await;
    assert_eq!(out.len(), 1, "exactly one WhatsApp: {out:?}");
    assert_eq!(out[0].0, json!(MARTA));
}

/// 🔴 whatsapp_inbox#279 word for word: an incomplete phone CONTAINED in Marta's number used to
/// find her conversation, and Marta got Lucía's «Confirmed!».
#[tokio::test]
async fn an_incomplete_phone_never_reaches_somebody_elses_chat() {
    let (rt, flow_id) = the_salon().await;
    confirm_with_phone(&rt, "apt-lucia", "600111").await;

    let (status, steps) = the_run(&rt, &flow_id).await;
    assert_eq!(sent(&rt).await, vec![], "nothing goes out, least of all to Marta");
    assert_eq!(status, store::STATUS_DONE, "stopping is the flow working, not a failure");
    assert_eq!(stopped_on(&steps), "phone_is_international");
}

#[tokio::test]
async fn a_phone_typed_with_spaces_stops_on_the_international_step() {
    let (rt, flow_id) = the_salon().await;
    confirm_with_phone(&rt, "apt-spaces", "600 111 222").await;

    let (_, steps) = the_run(&rt, &flow_id).await;
    assert_eq!(sent(&rt).await, vec![]);
    assert_eq!(stopped_on(&steps), "phone_is_international");
}

#[tokio::test]
async fn a_full_number_with_no_conversation_stops_on_the_thread_step() {
    let (rt, flow_id) = the_salon().await;
    confirm_with_phone(&rt, "apt-nochat", "+34600999888").await;

    let (_, steps) = the_run(&rt, &flow_id).await;
    assert_eq!(sent(&rt).await, vec![]);
    assert_eq!(stopped_on(&steps), "has_a_thread");
}

#[tokio::test]
async fn an_appointment_with_no_phone_stops_on_its_own_step() {
    let (rt, flow_id) = the_salon().await;
    confirm_with_phone(&rt, "apt-counter", "").await;

    let (_, steps) = the_run(&rt, &flow_id).await;
    assert_eq!(sent(&rt).await, vec![]);
    assert_eq!(stopped_on(&steps), "has_a_phone");
}

//! **The star case of ADR-0283, as far as a runtime without a network can carry it** (pm#112).
//!
//! ```text
//!  a customer's phone  →  SaaS  →  hub poller  →  core event `hub.whatsapp.message_received`
//!         ↓ relay: the manifest listener of `whatsapp_inbox` (this is what was MISSING)
//!  conversation + inbound message, phone normalised to E.164
//!         ↓ relay: the flow trigger (insert only)
//!  _flow_runs  →  flows_tick  →  step `notify` resolves the recipient through the grant
//!         ↓
//!  `flow.reminder.due` queued for +34600111222 — the answer the customer gets at 3 AM
//! ```
//!
//! Not a fixture: the modules installed here are the **published ones**, from
//! `modules-workspace/modules`, and the flow is the **template** shipped in
//! `whatsapp_inbox/flows/`. That is the point — the JSON Schema in `hub/schemas` is documentation,
//! `flows::def` is the authority, and the only way to know a template is real is to hand it to the
//! authority.
//!
//! What is NOT covered here, and cannot be: the `ai` steps. An agent turn is
//! `PendingIo::Ai`, dispatched by `crates/server` through the SaaS proxy with the hub's machine
//! token — there is no model at the end of a runtime test, by design (ARQUITECTURA.md §9.3).
//! What this test does pin is that the run REACHES that step and hands it over.
//!
//! Run with: `ERPLORA_MODULES_DIR=…/modules-workspace/modules DATABASE_URL=… cargo test -p
//! erplora-runtime --test whatsapp_appointment_e2e`
use std::path::PathBuf;

use erplora_db::{testutil::fresh_db, Params};
use erplora_runtime::flows::grants::{GrantKind, GrantSpec};
use erplora_runtime::flows::{store, NewFlow};
use erplora_runtime::{outbox, Runtime};
use serde_json::{json, Value};

const HUB: &str = "hub-wa-appointment-e2e";

/// Meta reports the sender WITHOUT a `+`. Everything downstream depends on that.
const WA_ID: &str = "34600111222";
const E164: &str = "+34600111222";

fn modules_dir() -> PathBuf {
    PathBuf::from(
        std::env::var("ERPLORA_MODULES_DIR")
            .expect("ERPLORA_MODULES_DIR must point at modules-workspace/modules"),
    )
}

fn module(id: &str) -> PathBuf {
    modules_dir().join(id)
}

fn template(name: &str) -> Value {
    let path = module("whatsapp_inbox").join("flows").join(name);
    serde_json::from_str(&std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{path:?}: {e}")))
        .expect("the template is JSON")
}

/// The sidecar's grants AS the hub installs them, pins included (hub#1623/#1662): a `payload` fixes
/// part of what the flow may send or read, and dropping it here would test a wider recipe than the
/// one that ships.
fn template_grants() -> Vec<GrantSpec> {
    let path = module("whatsapp_inbox")
        .join("flows")
        .join("appointment-from-whatsapp.grants.json");
    let body: Value = serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
    body["grants"]
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

/// A hub with the modules the peluquería actually has installed.
async fn runtime(ids: &[&str]) -> Runtime {
    let db = fresh_db().await;
    let mut rt = Runtime::with_hub_id(Box::new(db), HUB);
    rt.ensure_system_tables().await.unwrap();
    for id in ids {
        rt.install_from_dir(&module(id))
            .await
            .unwrap_or_else(|e| panic!("installing `{id}`: {e}"));
    }
    rt
}

async fn rows(rt: &Runtime, sql: &str) -> Vec<Value> {
    rt.db_for_test()
        .query(sql, &Params::new())
        .await
        .unwrap()
        .rows
}

/// Exactly what `crates/server/src/inbound_poll.rs::event_payload` writes, and exactly how it
/// writes it: the primary key derived from Meta's own message id.
async fn a_customer_writes(rt: &Runtime, wa_message_id: &str, text: &str) -> bool {
    let mut payload = Params::new();
    payload.insert("wa_message_id".into(), json!(wa_message_id));
    payload.insert("from".into(), json!(WA_ID));
    payload.insert("text".into(), json!(text));
    payload.insert("received_at".into(), json!("2026-08-11T03:04:05+00:00"));
    payload.insert(
        "message".into(),
        json!({ "id": wa_message_id, "from": WA_ID, "type": "text", "text": { "body": text } }),
    );
    outbox::insert_core_event_once(
        rt.db_for_test(),
        &format!("wa-{wa_message_id}"),
        HUB,
        "hub.whatsapp.message_received",
        &payload,
    )
    .await
    .unwrap()
}

/// The template with the `ai` steps removed (two since whatsapp_inbox#55 folded the reads back
/// into the step that acts on them): everything a runtime with no model can execute. The filter is
/// by `kind`, so it does not care how many there are.
fn acknowledge_only() -> Value {
    let mut def = template("appointment-from-whatsapp.es.flow.json");
    let steps: Vec<Value> = def["steps"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|s| s["kind"] != json!("ai"))
        .cloned()
        .collect();
    def["steps"] = json!(steps);
    def
}

async fn create(rt: &Runtime, definition: Value) -> String {
    rt.create_flow(
        &NewFlow {
            name: "WhatsApp → cita propuesta".into(),
            enabled: true,
            definition,
        },
        "hub_user:owner",
    )
    .await
    .unwrap()
    .id
}

// ── 1. the listener: the message LANDS, and the customer becomes reachable ─────────────────────

#[tokio::test]
async fn the_core_event_lands_in_the_inbox_and_the_phone_comes_out_diallable() {
    let rt = runtime(&["customers", "whatsapp_inbox"]).await;

    assert!(a_customer_writes(&rt, "wamid.AAA", "Hola, quiero pedir cita para un tinte").await);
    // Meta redelivers what it has not seen acknowledged. The primary key is the guarantee.
    assert!(
        !a_customer_writes(&rt, "wamid.AAA", "Hola, quiero pedir cita para un tinte").await,
        "a redelivered message must not become a second event"
    );

    rt.drain_outbox().await.unwrap();

    let convs = rows(
        &rt,
        "SELECT wa_contact_id, contact_phone, unread_count, status FROM whatsapp_inbox_conversation",
    )
    .await;
    assert_eq!(convs.len(), 1, "one contact, one thread");
    assert_eq!(convs[0]["wa_contact_id"], json!(WA_ID));
    assert_eq!(
        convs[0]["contact_phone"],
        json!(E164),
        "the phone the hub stores has to be the one it can dial"
    );
    assert_eq!(convs[0]["unread_count"], json!(1));

    let msgs = rows(
        &rt,
        "SELECT direction, message_type, body FROM whatsapp_inbox_message",
    )
    .await;
    assert_eq!(msgs.len(), 1, "exactly-once ingestion, not once per delivery");
    assert_eq!(msgs[0]["direction"], json!("inbound"));
    assert_eq!(
        msgs[0]["message_type"],
        json!("text"),
        "the type comes out of Meta's own object"
    );
    assert_eq!(msgs[0]["body"], json!("Hola, quiero pedir cita para un tinte"));

    assert!(
        rt.list_dead_events(10).await.unwrap().is_empty(),
        "nothing gave up on the way in"
    );
}

// ── 2. the template is a REAL document, and its grants are real grants ─────────────────────────

#[tokio::test]
async fn the_shipped_template_is_accepted_by_the_runtime_and_so_are_its_grants() {
    let rt = runtime(&[
        "customers",
        "taxes",
        "services",
        "staff",
        "schedules",
        "appointments",
        "whatsapp_inbox",
    ])
    .await;

    for name in [
        "appointment-from-whatsapp.en.flow.json",
        "appointment-from-whatsapp.es.flow.json",
    ] {
        let id = create(&rt, template(name)).await;
        rt.replace_flow_grants(&id, &template_grants(), "hub_user:owner")
            .await
            .unwrap_or_else(|e| panic!("{name}: the grants the template ships are refused: {e}"));
        let live = rt.list_flow_grants(&id).await.unwrap();
        assert_eq!(
            live.len(),
            template_grants().len(),
            "{name}: every grant the template asks for is live"
        );
    }
}

// ── 3. the chain: event → listener → trigger → the answer the customer gets ────────────────────

#[tokio::test]
async fn the_customer_who_writes_at_3am_gets_an_answer_addressed_by_the_grant() {
    let rt = runtime(&["customers", "whatsapp_inbox"]).await;
    let flow_id = create(&rt, acknowledge_only()).await;
    rt.replace_flow_grants(
        &flow_id,
        &[
            GrantSpec::pair(GrantKind::Notify, "whatsapp"),
            GrantSpec::pair(
                GrantKind::RecipientQuery,
                "whatsapp_inbox.conversations.list#contact_phone",
            ),
        ],
        "hub_user:owner",
    )
    .await
    .unwrap();

    a_customer_writes(&rt, "wamid.NIGHT", "buenas, quiero cita mañana para mechas").await;

    // The relay: the manifest listener FIRST (that is what creates the conversation the notify
    // step will read), then the flow trigger, which only inserts the run.
    rt.drain_outbox().await.unwrap();
    let runs = rt.list_flow_runs(&flow_id, 10, None).await.unwrap();
    assert_eq!(runs.len(), 1, "the core event started exactly one run");
    assert_eq!(runs[0].trigger_kind, "event");
    assert_eq!(
        runs[0].input,
        json!({
            "from": WA_ID,
            "text": "buenas, quiero cita mañana para mechas",
            "wa_message_id": "wamid.NIGHT",
            "received_at": "2026-08-11T03:04:05+00:00"
        }),
        "the trigger's input_map shaped the event into the run's input"
    );

    rt.process_flows().await.unwrap();

    let queued = rows(
        &rt,
        "SELECT payload, status FROM _event_outbox WHERE event_name = 'flow.reminder.due'",
    )
    .await;
    assert_eq!(queued.len(), 1, "one message was queued for the customer");
    let payload: Value = serde_json::from_str(queued[0]["payload"].as_str().unwrap()).unwrap();
    assert_eq!(payload["channel"], json!("whatsapp"));
    assert_eq!(
        payload["to"],
        json!(E164),
        "the recipient came out of the granted read, in the only shape the hub can dial"
    );
    assert!(
        payload["vars"]["text"]
            .as_str()
            .unwrap()
            .contains("en cuanto abramos"),
        "the customer is told they will be confirmed when the salon opens: {payload}"
    );
    assert!(
        payload["resolved_via"]
            .as_str()
            .unwrap()
            .starts_with("flow_grant:"),
        "the queued row names the grant that authorised it, so revoking it stops the message"
    );

    let run = rt.list_flow_runs(&flow_id, 10, None).await.unwrap().remove(0);
    assert_eq!(run.status, store::STATUS_DONE);
}

// ── 4. and with the ai steps in, the run gets as far as a runtime can ──────────────────────────

#[tokio::test]
async fn with_the_ai_steps_the_run_reaches_them_and_hands_over_to_the_server() {
    let rt = runtime(&[
        "customers",
        "taxes",
        "services",
        "staff",
        "schedules",
        "appointments",
        "whatsapp_inbox",
    ])
    .await;
    let flow_id = create(&rt, template("appointment-from-whatsapp.es.flow.json")).await;
    rt.replace_flow_grants(&flow_id, &template_grants(), "hub_user:owner")
        .await
        .unwrap();

    a_customer_writes(&rt, "wamid.FULL", "hola! quiero cita para un tinte").await;
    rt.drain_outbox().await.unwrap();

    let report = rt.process_flows().await.unwrap();

    let (run, steps) = {
        let run = rt.list_flow_runs(&flow_id, 10, None).await.unwrap().remove(0);
        rt.get_flow_run(&run.id).await.unwrap()
    };
    assert_eq!(
        steps.first().map(|s| s.step_id.as_str()),
        Some("acknowledge"),
        "the customer is answered BEFORE anything is reasoned about"
    );
    assert_eq!(steps[0].status, "done");
    assert!(
        steps.len() >= 2 && steps[1].step_id == "know_the_customer",
        "the run reached the first agent step: {steps:?}"
    );
    assert_eq!(
        run.status,
        store::STATUS_RUNNING,
        "the run keeps its lease while the server talks to the model"
    );
    assert!(
        !report.pending_io.is_empty(),
        "the tick handed the agent turn to the server, outside the global lock"
    );
}

// ── 5. whatsapp_inbox#165: the recipe knows a customer on file, however her phone was typed ────

/// A customer of years writes in, and the salon typed her phone the way phones are typed in
/// Spain — no country code, spaces. WhatsApp hands the recipe `34600111222`. Over `customers.list`
/// the lookup was a LIKE on the raw text, so `find_customer` answered «nobody», the agent step was
/// told she was new, and it created a SECOND card and booked on it. The read has to compare
/// NUMBERS (`customers.by_phone`, customers#79) — and only the runtime can say that the shipped
/// step, its grant and the neighbour's query really fit together.
#[tokio::test]
async fn the_recipe_finds_the_customer_on_file_however_the_salon_typed_her_phone() {
    let rt = runtime(&[
        "customers",
        "taxes",
        "services",
        "staff",
        "schedules",
        "appointments",
        "whatsapp_inbox",
    ])
    .await;
    let owner = erplora_runtime::RequestContext::new(HUB, "owner", ["*".to_string()]);
    let card: Params = json!({ "name": "Ana de siempre", "phone": "600 111 222" })
        .as_object()
        .unwrap()
        .clone()
        .into_iter()
        .collect();
    rt.execute_command("customers.create", &card, &owner)
        .await
        .expect("the salon's card for Ana");
    let ana = rows(&rt, "SELECT id FROM customers_customer WHERE name = 'Ana de siempre'").await;
    let ana = ana[0]["id"].as_str().unwrap().to_string();

    // Only the TYPED-message trigger. The template also declares the tapped-option one on the same
    // event, and the kernel keeps ONE trigger per event and flow (the last): with both, a typed
    // message starts nothing at all — hub#2061. What this test is about starts after the trigger.
    let mut definition = template("appointment-from-whatsapp.es.flow.json");
    let typed = definition["triggers"][0].clone();
    assert_eq!(typed["filter"]["event.text"], json!({ "neq": "" }), "triggers[0] is the typed one");
    definition["triggers"] = json!([typed]);
    let flow_id = create(&rt, definition).await;
    rt.replace_flow_grants(&flow_id, &template_grants(), "hub_user:owner")
        .await
        .unwrap();

    // Exactly the keys `crates/server/src/inbound_poll.rs::event_payload` writes since hub#1621:
    // the recipe's trigger answers a customer writing NOW, not the owner's reply or the backlog.
    let payload: Params = json!({
        "wa_message_id": "wamid.ANA",
        "from": WA_ID,
        "direction": "inbound",
        "contact": WA_ID,
        "source": "live",
        "text": "hola! quiero cita para un tinte",
        "received_at": "2026-09-24T09:00:00+00:00",
        "message": { "id": "wamid.ANA", "from": WA_ID, "type": "text",
                     "text": { "body": "hola! quiero cita para un tinte" } },
    })
    .as_object()
    .unwrap()
    .clone()
    .into_iter()
    .collect();
    assert!(outbox::insert_core_event_once(
        rt.db_for_test(),
        "wa-wamid.ANA",
        HUB,
        "hub.whatsapp.message_received",
        &payload,
    )
    .await
    .unwrap());
    rt.drain_outbox().await.unwrap();
    rt.process_flows().await.unwrap();

    let runs = rt.list_flow_runs(&flow_id, 10, None).await.unwrap();
    assert_eq!(runs.len(), 1, "her message started the recipe");
    let (_, steps) = rt.get_flow_run(&runs[0].id).await.unwrap();
    let find = steps
        .iter()
        .find(|s| s.step_id == "find_customer")
        .unwrap_or_else(|| panic!("the run reached `find_customer`: {steps:?}"));
    assert_eq!(find.status, "done", "the read ran under the recipe's own grant: {find:?}");
    assert_eq!(
        find.output["found"],
        json!(true),
        "Ana is on file as `600 111 222` and wrote from {WA_ID}: the recipe must know her, or it \
         creates her a second card — {find:?}"
    );
    assert_eq!(find.output["count"], json!(1), "one card carries that number: {find:?}");
    assert_eq!(find.output["id"], json!(ana), "and it is HER card: {find:?}");
    assert!(
        steps.iter().any(|s| s.step_id == "know_the_customer"),
        "the run went on to the agent step, which is now told she is on file: {steps:?}"
    );
}

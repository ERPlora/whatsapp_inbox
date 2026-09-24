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
    grants_of("appointment-from-whatsapp.grants.json")
}

/// The pinned grants of any recipe's sidecar, read the same way as [`template_grants`].
fn grants_of(sidecar: &str) -> Vec<GrantSpec> {
    let path = module("whatsapp_inbox").join("flows").join(sidecar);
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

// ── 6. whatsapp_inbox#76: «el 2» — the list she was offered is there for her next message ──────

/// A typed message from Ana, with the keys `inbound_poll.rs::event_payload` writes (hub#1621).
async fn ana_writes(rt: &Runtime, wa_message_id: &str, text: &str) {
    let payload: Params = json!({
        "wa_message_id": wa_message_id,
        "from": WA_ID,
        "direction": "inbound",
        "contact": WA_ID,
        "source": "live",
        "text": text,
        "received_at": "2026-09-24T09:00:00+00:00",
        "message": { "id": wa_message_id, "from": WA_ID, "type": "text", "text": { "body": text } },
    })
    .as_object()
    .unwrap()
    .clone()
    .into_iter()
    .collect();
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

/// Drives the ONE run of this message to its end, standing in for the model: every agent turn the
/// tick hands over is answered with what `answer` says for that step. Returns the run's steps as
/// the kernel recorded them. Before answering `ai_step` (`book_appointment`, `book_table`), `seen`
/// gets the steps recorded so far — that is what the agent would have been briefed with.
async fn drive(
    rt: &Runtime,
    flow_id: &str,
    ai_step: &str,
    run_index: usize,
    answer: impl Fn(&str) -> Value,
    seen: &mut Vec<store::FlowRunStep>,
) -> Vec<store::FlowRunStep> {
    for _ in 0..30 {
        let report = rt.process_flows().await.unwrap();
        for io in report.pending_io {
            if io.step_id() == ai_step {
                *seen = rt.get_flow_run(io.run_id()).await.unwrap().1;
            }
            rt.complete_flow_io(
                io.run_id(),
                io.step_id(),
                erplora_runtime::flows::executor::IoResult::Done(answer(io.step_id())),
            )
            .await
            .unwrap();
        }
        let runs = rt.list_flow_runs(flow_id, 10, None).await.unwrap();
        assert_eq!(runs.len(), run_index + 1, "each message starts exactly one run");
        // Newest first: this message's run is the first one.
        let ended = [store::STATUS_DONE, store::STATUS_FAILED, store::STATUS_CANCELLED];
        if ended.contains(&runs[0].status.as_str()) {
            return rt.get_flow_run(&runs[0].id).await.unwrap().1;
        }
    }
    panic!("the run of message #{run_index} never finished");
}

fn step<'a>(steps: &'a [store::FlowRunStep], id: &str) -> &'a store::FlowRunStep {
    steps
        .iter()
        .find(|s| s.step_id == id)
        .unwrap_or_else(|| panic!("the run reached `{id}`: {steps:?}"))
}

/// What the conversation remembers as on offer — the column `remember_offer` writes.
async fn remembered(rt: &Runtime) -> String {
    let r = rows(
        rt,
        &format!("SELECT offered_slots FROM whatsapp_inbox_conversation WHERE wa_contact_id = '{WA_ID}'"),
    )
    .await;
    r[0]["offered_slots"].as_str().unwrap_or_default().to_string()
}

/// Ana asks for a slot and is offered two. She answers «el 2» — a fresh run. That run has to find
/// the two slots she was offered BEFORE its agent step, or «el 2» points at nothing and she is
/// offered the list again (the bug). Once she has booked, the list is cleared: a «el 2» written
/// later finds nothing to point at.
#[tokio::test]
async fn her_typed_choice_finds_the_list_she_was_offered() {
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
    let card: Params = json!({ "name": "Ana", "phone": E164 })
        .as_object()
        .unwrap()
        .clone()
        .into_iter()
        .collect();
    rt.execute_command("customers.create", &card, &owner).await.expect("Ana's card");

    // Only the TYPED trigger: with both, the kernel keeps the tapped one and a typed message starts
    // nothing (hub#2061). This test is about what happens once it starts.
    let mut definition = template("appointment-from-whatsapp.es.flow.json");
    let typed = definition["triggers"][0].clone();
    assert_eq!(typed["filter"]["event.text"], json!({ "neq": "" }), "triggers[0] is the typed one");
    definition["triggers"] = json!([typed]);
    let flow_id = create(&rt, definition).await;
    rt.replace_flow_grants(&flow_id, &template_grants(), "hub_user:owner")
        .await
        .unwrap();

    let offered = json!([
        { "id": "2026-09-25T10:00|staff:1|service:3", "title": "jue 10:00 · Ana" },
        { "id": "2026-09-25T12:30|staff:1|service:3", "title": "jue 12:30 · Ana" },
    ]);
    let mut seen = Vec::new();

    // 1) «¿tenéis hueco mañana?» → two slots offered.
    ana_writes(&rt, "wamid.ASK", "¿tenéis hueco mañana para un corte?").await;
    let first = drive(
        &rt,
        &flow_id,
        "book_appointment",
        0,
        |id| match id {
            "book_appointment" => json!({ "text": "Mañana tengo estos:", "slots": offered.clone() }),
            _ => json!({ "text": "Ana, en la ficha" }),
        },
        &mut seen,
    )
    .await;
    assert_eq!(
        step(&seen, "recall_offer").output["found"],
        json!(false),
        "before anything was offered there is nothing to recall"
    );
    assert_eq!(step(&first, "remember_offer").status, "done", "{first:?}");
    let stored: Value = serde_json::from_str(&remembered(&rt).await).expect("the list is JSON");
    assert_eq!(stored, offered, "the conversation remembers the list she was offered");

    // 2) «el 2» → a fresh run, whose agent step is briefed with that list.
    ana_writes(&rt, "wamid.TWO", "el 2").await;
    let second = drive(
        &rt,
        &flow_id,
        "book_appointment",
        1,
        |id| match id {
            "book_appointment" => json!({ "text": "Reservada el jueves a las 12:30 con Ana.", "slots": [] }),
            _ => json!({ "text": "Ana, en la ficha" }),
        },
        &mut seen,
    )
    .await;
    let recall = step(&seen, "recall_offer");
    assert_eq!(recall.output["found"], json!(true), "«el 2» finds the list: {recall:?}");
    let recalled: Value = serde_json::from_str(recall.output["offered_slots"].as_str().unwrap())
        .expect("the recalled list is JSON");
    assert_eq!(recalled, offered, "the SAME list, in the order she saw it");
    assert_eq!(step(&second, "remember_offer").status, "done", "{second:?}");
    assert_eq!(remembered(&rt).await, "[]", "once she booked, nothing is on offer any more");

    // 3) a stray «el 2» later points at nothing.
    ana_writes(&rt, "wamid.LATER", "el 2").await;
    drive(
        &rt,
        &flow_id,
        "book_appointment",
        2,
        |id| match id {
            "book_appointment" => json!({ "text": "¿Qué día te viene bien?", "slots": [] }),
            _ => json!({ "text": "Ana, en la ficha" }),
        },
        &mut seen,
    )
    .await;
    assert_eq!(
        step(&seen, "recall_offer").output["found"],
        json!(false),
        "a cleared offer is not recalled"
    );
}

// ── 7. whatsapp_inbox#174: «la 2» — the same for the times a restaurant offered ────────────────

/// The restaurant recipe answers «¿tenéis mesa esta noche para 4?» with a list of times, exactly
/// like the salon one answers with slots. A guest who WRITES «la 2» starts a fresh run, and that run
/// has to find the times they were offered BEFORE `book_table`, or it offers them all over again.
/// Once the table is booked the list is cleared, so a later «la 2» points at nothing.
#[tokio::test]
async fn their_typed_choice_finds_the_table_times_they_were_offered() {
    let rt = runtime(&["customers", "tables", "reservations", "whatsapp_inbox"]).await;

    // Only the TYPED trigger, for the same reason as above (hub#2061).
    let mut definition = template("reservation-from-whatsapp.es.flow.json");
    let typed = definition["triggers"][0].clone();
    assert_eq!(typed["filter"]["event.text"], json!({ "neq": "" }), "triggers[0] is the typed one");
    definition["triggers"] = json!([typed]);
    let flow_id = create(&rt, definition).await;
    rt.replace_flow_grants(
        &flow_id,
        &grants_of("reservation-from-whatsapp.grants.json"),
        "hub_user:owner",
    )
    .await
    .unwrap();

    let offered = json!([
        { "id": "2026-09-24T21:00|party:4", "title": "hoy 21:00" },
        { "id": "2026-09-24T21:30|party:4", "title": "hoy 21:30" },
    ]);
    let mut seen = Vec::new();

    // 1) «¿tenéis mesa esta noche para 4?» → two times offered.
    ana_writes(&rt, "wamid.TABLE", "¿tenéis mesa esta noche para 4?").await;
    let first = drive(
        &rt,
        &flow_id,
        "book_table",
        0,
        |_| json!({ "text": "Esta noche para cuatro tengo:", "slots": offered.clone() }),
        &mut seen,
    )
    .await;
    assert_eq!(
        step(&seen, "recall_offer").output["found"],
        json!(false),
        "before anything was offered there is nothing to recall"
    );
    assert_eq!(step(&first, "remember_offer").status, "done", "{first:?}");
    let stored: Value = serde_json::from_str(&remembered(&rt).await).expect("the list is JSON");
    assert_eq!(stored, offered, "the conversation remembers the times they were offered");

    // 2) «la 2» → a fresh run, whose agent step is briefed with that list.
    ana_writes(&rt, "wamid.TABLE2", "la 2").await;
    let second = drive(
        &rt,
        &flow_id,
        "book_table",
        1,
        |_| json!({ "text": "Mesa para cuatro hoy a las 21:30.", "slots": [] }),
        &mut seen,
    )
    .await;
    let recall = step(&seen, "recall_offer");
    assert_eq!(recall.output["found"], json!(true), "«la 2» finds the list: {recall:?}");
    let recalled: Value = serde_json::from_str(recall.output["offered_slots"].as_str().unwrap())
        .expect("the recalled list is JSON");
    assert_eq!(recalled, offered, "the SAME list, in the order they saw it");
    assert_eq!(step(&second, "remember_offer").status, "done", "{second:?}");
    assert_eq!(remembered(&rt).await, "[]", "once the table is booked, nothing is on offer");

    // 3) a stray «la 2» later points at nothing.
    ana_writes(&rt, "wamid.TABLE3", "la 2").await;
    drive(
        &rt,
        &flow_id,
        "book_table",
        2,
        |_| json!({ "text": "¿Para qué día y cuántos sois?", "slots": [] }),
        &mut seen,
    )
    .await;
    assert_eq!(
        step(&seen, "recall_offer").output["found"],
        json!(false),
        "a cleared offer is not recalled"
    );
}

// ── 8. whatsapp_inbox#83: her card could not be created, and she is answered all the same ──────

/// A new customer writes and `know_the_customer` cannot give her a card: `customers.create` is
/// refused (a duplicate number, a field the module rejects). Under `policy: "auto"` that refusal
/// goes back into the agent's turn as a tool result (`crates/server/src/agent_runner.rs::dispatch`),
/// so the step ends `done` with prose about the failure and NO card behind it. From there the run
/// has to carry on to the step that talks to her — through a lookup that finds nobody, a link that
/// has no id to link and a booking step briefed with `count: 0` — and queue that answer. A step on
/// that path that stops the run on an empty card leaves her with «let me check the diary» and then
/// silence, which is exactly what #83 reports.
#[tokio::test]
async fn when_her_card_cannot_be_created_she_is_still_answered() {
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

    // Only the TYPED trigger (hub#2061), as in the tests above.
    let mut definition = template("appointment-from-whatsapp.es.flow.json");
    let typed = definition["triggers"][0].clone();
    assert_eq!(typed["filter"]["event.text"], json!({ "neq": "" }), "triggers[0] is the typed one");
    definition["triggers"] = json!([typed]);
    let flow_id = create(&rt, definition).await;
    rt.replace_flow_grants(&flow_id, &template_grants(), "hub_user:owner")
        .await
        .unwrap();

    const SORRY: &str = "No he podido apuntarte todavía; alguien del salón te escribe enseguida.";
    let mut seen = Vec::new();
    ana_writes(&rt, "wamid.NOCARD", "hola, soy Ana, ¿tenéis hueco mañana?").await;
    let steps = drive(
        &rt,
        &flow_id,
        "book_appointment",
        0,
        |id| match id {
            // What the model writes after `customers.create` came back as `{"error": …}`.
            "know_the_customer" => json!({ "text": "customers.create was refused; no card exists" }),
            "book_appointment" => json!({ "text": SORRY, "slots": [] }),
            other => panic!("no other step is an agent turn: {other}"),
        },
        &mut seen,
    )
    .await;

    assert!(
        rows(&rt, "SELECT id FROM customers_customer").await.is_empty(),
        "the premise: nobody is on file"
    );
    let resolved = step(&seen, "resolve_customer");
    assert_eq!(resolved.output["found"], json!(false), "{resolved:?}");
    assert_eq!(
        resolved.output["count"],
        json!(0),
        "the booking step is briefed that no single card answers her number: {resolved:?}"
    );

    let runs = rt.list_flow_runs(&flow_id, 10, None).await.unwrap();
    assert_eq!(runs[0].status, store::STATUS_DONE, "the run did not stop on the missing card: {steps:?}");
    assert_eq!(step(&steps, "confirm_to_customer").status, "done", "{steps:?}");

    let answers: Vec<Value> = rows(
        &rt,
        "SELECT payload FROM _event_outbox WHERE event_name = 'flow.reminder.due'",
    )
    .await
    .iter()
    .map(|r| serde_json::from_str(r["payload"].as_str().unwrap()).unwrap())
    .collect();
    assert!(
        answers
            .iter()
            .any(|p| p["to"] == json!(E164) && p["vars"]["text"] == json!(SORRY)),
        "after «let me check the diary», what the booking step wrote reaches HER: {answers:?}"
    );
}

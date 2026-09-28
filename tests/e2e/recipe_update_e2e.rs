//! **A reply the business turned on BEFORE an improvement gets the improvement only when she says
//! so — and the WhatsApp screen's «Actualizar» is the door that hands it over** (whatsapp_inbox#241).
//!
//! ```text
//!  she turns the WhatsApp reply on (old recipe)   →  flow built, digest of THAT recipe stored
//!  the module is updated (new recipe)             →  the flow is NOT touched (hub#1684/#2059)
//!                                                 →  the listing reads `installed.outdated = true`
//!  she taps «Actualizar» on the WhatsApp screen   →  `restoreTemplate(family)`, this module's door
//!                                                 →  same flow, new document, on/off untouched
//! ```
//!
//! The screen itself is pinned in `ui/…/erp-whatsapp-inbox-settings.test.ts`; what only a real
//! runtime can say is that the two facts it stands on are true for THIS module's recipe: the hub
//! flags the flow she activated as outdated after the update, and the restore door rebuilds it from
//! the current recipe without switching anything on or off. The last test is the reason the issue
//! exists: before the update-through-the-screen, a silent assistant still texted her customer an
//! EMPTY WhatsApp (the probe of whatsapp_inbox#239); after it, the customer gets the apology.
//!
//! «Old» is synthesised from the recipe that ships, not checked out from a tag: the copy drops the
//! silence apology and the guard on the confirmation — exactly the shape v2.1.94 had — so the test
//! keeps meaning the same thing on every future release instead of pinning one.
//!
//! Run with: `ERPLORA_MODULES_DIR=…/modules-workspace/modules DATABASE_URL=… cargo test -p
//! erplora-runtime --test recipe_update_e2e` (see `README.md` next to this file).
use std::path::{Path, PathBuf};

use erplora_db::{testutil::fresh_db, Params};
use erplora_runtime::flows::executor::IoResult;
use erplora_runtime::flows::{templates, Flow};
use erplora_runtime::{outbox, Runtime};
use serde_json::{json, Value};

const HUB: &str = "hub-wa-recipe-update-e2e";
const MODULE: &str = "whatsapp_inbox";
const FAMILY: &str = "appointment-from-whatsapp";
const OWNER: &str = "hub_user:owner";
const WA_ID: &str = "34600111222";
/// The step the old recipe did not have (whatsapp_inbox#239).
const SILENCE_STEP: &str = "sorry_book_appointment_said_nothing";

fn modules_dir() -> PathBuf {
    PathBuf::from(
        std::env::var("ERPLORA_MODULES_DIR")
            .expect("ERPLORA_MODULES_DIR must point at modules-workspace/modules"),
    )
}

fn module(id: &str) -> PathBuf {
    modules_dir().join(id)
}

/// The module as published, minus what a release does not carry (dependencies, git, build cache).
fn copy_tree(from: &Path, to: &Path) {
    std::fs::create_dir_all(to).unwrap();
    for entry in std::fs::read_dir(from).unwrap() {
        let entry = entry.unwrap();
        let name = entry.file_name();
        if [".git", "node_modules", "target"].iter().any(|skip| name == *skip) {
            continue;
        }
        let target = to.join(&name);
        if entry.file_type().unwrap().is_dir() {
            copy_tree(&entry.path(), &target);
        } else {
            std::fs::copy(entry.path(), &target).unwrap();
        }
    }
}

/// This module with its booking recipe as it shipped BEFORE whatsapp_inbox#239: no silence apology,
/// and a confirmation that goes out whatever the assistant said — empty included.
fn older_release(tag: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("wa241-{tag}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    copy_tree(&module(MODULE), &dir);
    for lang in ["en", "es"] {
        let path = dir.join("flows").join(format!("{FAMILY}.{lang}.flow.json"));
        let mut doc: Value = serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
        let steps = doc["steps"].as_array_mut().expect("a recipe has steps");
        let before = steps.len();
        steps.retain(|s| s["id"] != SILENCE_STEP);
        assert_eq!(steps.len(), before - 1, "{path:?} no longer carries `{SILENCE_STEP}`: the «old» recipe is the new one");
        for step in steps.iter_mut().filter(|s| s["id"] == "confirm_to_customer") {
            step.as_object_mut().unwrap().remove("run_if");
        }
        std::fs::write(&path, serde_json::to_string_pretty(&doc).unwrap()).unwrap();
    }
    dir
}

/// A salon on the OLD recipe: the booking neighbours, this module at its older release, and the
/// WhatsApp reply turned on through this module's own door — what «Activar» on the screen does.
async fn salon_on_the_old_recipe(tag: &str) -> (Runtime, String) {
    let mut rt = Runtime::with_hub_id(Box::new(fresh_db().await), HUB);
    rt.ensure_system_tables().await.unwrap();
    for id in ["customers", "taxes", "services", "staff", "schedules", "appointments"] {
        rt.install_from_dir(&module(id))
            .await
            .unwrap_or_else(|e| panic!("installing {id}: {e}"));
    }
    rt.install_from_dir(&older_release(tag)).await.unwrap();
    let activation = rt.activate_flow_template(MODULE, FAMILY, OWNER).await.unwrap();
    (rt, activation.flow.id)
}

fn step_ids(flow: &Flow) -> Vec<String> {
    flow.definition["steps"]
        .as_array()
        .unwrap()
        .iter()
        .map(|s| s["id"].as_str().unwrap().to_string())
        .collect()
}

/// `installed.outdated` of `GET /api/hub/flows/templates` for this family — the one comparison
/// `crates/server/src/flows_api.rs` makes (stored digest vs the recipe served NOW), which is the
/// field the WhatsApp screen reads to paint «Hay una versión mejorada».
async fn outdated(rt: &Runtime) -> Option<bool> {
    let installed = rt.installed_flow_templates().await.unwrap();
    let (_, _, stored) = installed
        .get(&templates::template_ref(MODULE, FAMILY))
        .expect("the family was activated, so the hub lists it as installed");
    let (_, served) = rt
        .registry()
        .flow_templates()
        .into_iter()
        .find(|(m, t)| *m == MODULE && t.family == FAMILY)
        .expect("the hub serves this family");
    stored.as_ref().map(|digest| *digest != templates::recipe_digest(served))
}

/// She writes; the assistant looks at the diary and says NOTHING. Returns what was queued to her.
async fn a_silent_assistant_answers(rt: &Runtime, wamid: &str) -> Vec<Value> {
    let mut payload = Params::new();
    for (k, v) in [
        ("wa_message_id", json!(wamid)),
        ("from", json!(WA_ID)),
        ("direction", json!("inbound")),
        ("source", json!("live")),
        ("text", json!("hola, quiero cita")),
        ("received_at", json!("2026-09-28T09:00:00+00:00")),
    ] {
        payload.insert(k.into(), v);
    }
    let id = format!("wa-{wamid}");
    assert!(outbox::insert_core_event_once(rt.db_for_test(), &id, HUB, "hub.whatsapp.message_received", &payload)
        .await
        .unwrap());
    rt.drain_outbox().await.unwrap();
    for _ in 0..30 {
        let report = rt.process_flows().await.unwrap();
        for io in report.pending_io {
            let answer = match io.step_id() {
                "know_the_customer" => json!({ "text": "card ok" }),
                _ => json!({ "text": "", "tool_calls": [], "slots": [] }),
            };
            rt.complete_flow_io(io.run_id(), io.step_id(), IoResult::Done(answer)).await.unwrap();
        }
    }
    let rows = rt
        .db_for_test()
        .query(
            "SELECT payload FROM _event_outbox WHERE event_name = 'flow.reminder.due' ORDER BY created_at",
            &Params::new(),
        )
        .await
        .unwrap()
        .rows;
    rows.iter()
        .map(|r| serde_json::from_str::<Value>(r["payload"].as_str().unwrap()).unwrap()["vars"]["text"].clone())
        .collect()
}

#[tokio::test]
async fn updating_the_module_leaves_her_reply_as_it_was_and_the_hub_flags_it_outdated() {
    let (mut rt, flow_id) = salon_on_the_old_recipe("flag").await;
    assert_eq!(outdated(&rt).await, Some(false), "freshly built from the recipe it was built from");

    rt.update_from_dir(&module(MODULE)).await.unwrap();

    let flow = rt.get_flow(&flow_id).await.unwrap();
    assert!(
        !step_ids(&flow).iter().any(|s| s == SILENCE_STEP),
        "the update rewrote her automation on its own — hub#2059 says nothing is overwritten silently"
    );
    assert!(flow.enabled, "the update switched her reply off");
    assert_eq!(
        outdated(&rt).await,
        Some(true),
        "the hub does not flag the reply she turned on as outdated: the WhatsApp screen has nothing to read"
    );
}

#[tokio::test]
async fn the_modules_own_restore_door_hands_her_the_new_reply_and_keeps_it_running() {
    let (mut rt, flow_id) = salon_on_the_old_recipe("restore").await;
    rt.update_from_dir(&module(MODULE)).await.unwrap();

    // Why the screen offers restore and not a second «Activar»: activating an existing flow is a
    // switch that never touches the document (hub#1684), so it cannot be the way the update lands.
    rt.activate_flow_template(MODULE, FAMILY, OWNER).await.unwrap();
    let flow = rt.get_flow(&flow_id).await.unwrap();
    assert!(!step_ids(&flow).iter().any(|s| s == SILENCE_STEP), "activating again now updates the recipe: the restore door is no longer the only way");

    let restored = rt.restore_flow_template(MODULE, FAMILY, OWNER).await.unwrap();

    assert_eq!(restored.id, flow_id, "a restore is the same flow — its history keeps an owner");
    let flow = rt.get_flow(&flow_id).await.unwrap();
    assert!(step_ids(&flow).iter().any(|s| s == SILENCE_STEP), "still the old recipe after «Actualizar»");
    assert!(flow.enabled, "updating switched her running reply off");
    assert_eq!(outdated(&rt).await, Some(false), "the notice would stay on after updating");
}

#[tokio::test]
async fn a_paused_reply_is_updated_and_stays_paused() {
    let (mut rt, flow_id) = salon_on_the_old_recipe("paused").await;
    rt.deactivate_flow_template(MODULE, FAMILY, OWNER).await.unwrap();
    rt.update_from_dir(&module(MODULE)).await.unwrap();
    assert_eq!(outdated(&rt).await, Some(true), "a paused reply is outdated too: switching it on would run the old one");

    rt.restore_flow_template(MODULE, FAMILY, OWNER).await.unwrap();

    let flow = rt.get_flow(&flow_id).await.unwrap();
    assert!(step_ids(&flow).iter().any(|s| s == SILENCE_STEP));
    assert!(!flow.enabled, "«Actualizar» switched on a reply she had paused");
}

#[tokio::test]
async fn after_updating_a_silent_assistant_gets_her_the_apology_not_an_empty_whatsapp() {
    let (mut rt, _) = salon_on_the_old_recipe("silence").await;
    rt.update_from_dir(&module(MODULE)).await.unwrap();

    // Control: the module is updated but she has not tapped «Actualizar» — the harm of the issue.
    let before = a_silent_assistant_answers(&rt, "wamid.W241a").await;
    assert!(
        before.contains(&json!("")),
        "the old recipe no longer sends an empty WhatsApp — this test stopped proving anything: {before:?}"
    );

    rt.restore_flow_template(MODULE, FAMILY, OWNER).await.unwrap();
    let after = a_silent_assistant_answers(&rt, "wamid.W241b").await;
    let new_ones = &after[before.len()..];
    assert!(!new_ones.contains(&json!("")), "still texted her an empty WhatsApp after updating: {new_ones:?}");
    let apology = rt
        .get_flow(&rt.installed_flow_templates().await.unwrap()[&templates::template_ref(MODULE, FAMILY)].0)
        .await
        .unwrap()
        .definition["steps"]
        .as_array()
        .unwrap()
        .iter()
        .find(|s| s["id"] == SILENCE_STEP)
        .unwrap()["vars"]["text"]
        .clone();
    assert!(new_ones.contains(&apology), "she did not get the apology: {new_ones:?}");
}

//! Handler WASM (Tier 2) del módulo `whatsapp_inbox`.
//! Lógica pura, sin BD: recibe `{payload, context}` y devuelve **intenciones**
//! (operaciones SQL del propio módulo) que el host valida y ejecuta en una
//! transacción. Los eventos los emite el runtime vía el `emit` declarado en
//! `module.json` (no se duplican aquí).
//!
//! Exporta tres funciones:
//! * `fulfill_request` — cumplir una request (portado de
//!   `RequestService.fulfill_request`, ver `WASM-TODO.md` §1).
//! * `parse_inbound_message` — crear la request parseada por el LLM (pieza 3 de
//!   `WASM-TODO.md`; la persistencia del mensaje inbound la cubre el command
//!   Tier-0 `whatsapp_inbox.messages.ingest`).
//! * `link_known_customer` — links a conversation to the customer on file for the number that
//!   wrote, with no automation installed (whatsapp_inbox#149).
//!
//! Ramas:
//! * `create_linked_object = false` (default) — transición simple a `fulfilled`.
//!   La guarda de estado (**solo** desde `confirmed`) es DOBLE desde whatsapp_inbox#40:
//!   el WHERE de `commands/_fulfill_transition.sql` (red de seguridad ante una carrera) y
//!   ESTE handler, que pre-carga la request con `reads` (ADR-0069) y rechaza con un código
//!   de dominio si no está `confirmed` — un `WHERE` que no casa nada commitea igual y el
//!   command devolvía `ok: true` con `whatsapp_inbox.request.fulfilled` publicado para algo
//!   que no ocurrió (el `expect_rows` del manifest no llega a los Tier-2: cuenta las filas
//!   del bloque `sql`, que aquí está vacío — ERPlora/tasks#26).
//! * `create_linked_object = true` — dispatch cross-módulo (crear el objeto en el
//!   módulo destino vía su command público y enlazar `linked_module`/
//!   `linked_object_id`). **NO soportado todavía**: el runtime rechaza
//!   operaciones de handlers sobre commands de otros módulos
//!   (`validate_operation`, aislamiento ARQUITECTURA.md §5.3) y no existe la
//!   capacidad de lecturas pre-cargadas (settings.`output_modules`, request).
//!   Hasta que esa decisión de modelo de comandos se tome (issue #3/#5), esta
//!   rama devuelve el error explícito `cross_module_dispatch_unsupported`.

use erplora_guest_sdk::{DomainError, Operation, Output};
use serde_json::{json, Map, Value};

#[cfg(feature = "guest")]
use extism_pdk::*;

#[cfg(feature = "guest")]
#[plugin_fn]
pub fn fulfill_request(input: Json<erplora_guest_sdk::Input>) -> FnResult<Json<Output>> {
    match fulfill_request_pure(input.into_inner().into_value()) {
        Ok(out) => Ok(Json(out)),
        Err(msg) => Err(WithReturnCode::new(Error::msg(msg), 1)),
    }
}

#[cfg(feature = "guest")]
#[plugin_fn]
pub fn parse_inbound_message(input: Json<erplora_guest_sdk::Input>) -> FnResult<Json<Output>> {
    match parse_inbound_message_pure(input.into_inner().into_value()) {
        Ok(out) => Ok(Json(out)),
        Err(msg) => Err(WithReturnCode::new(Error::msg(msg), 1)),
    }
}

#[cfg(feature = "guest")]
#[plugin_fn]
pub fn link_known_customer(input: Json<erplora_guest_sdk::Input>) -> FnResult<Json<Output>> {
    match link_known_customer_pure(input.into_inner().into_value()) {
        Ok(out) => Ok(Json(out)),
        Err(msg) => Err(WithReturnCode::new(Error::msg(msg), 1)),
    }
}

fn as_str(v: &Value) -> String {
    match v {
        Value::String(s) => s.clone(),
        Value::Number(n) => n.to_string(),
        _ => String::new(),
    }
}

fn as_bool(v: &Value) -> bool {
    match v {
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_i64().unwrap_or(0) != 0,
        Value::String(s) => matches!(s.as_str(), "1" | "true" | "True" | "yes"),
        _ => false,
    }
}

/// Rows of a pre-loaded read (`context.reads`, ADR-0069 §1). `None` = the read did not arrive
/// (≠ arrived empty, which means "there is no such row").
fn read_rows<'a>(input: &'a Value, query: &str) -> Option<&'a Vec<Value>> {
    input.get("context")?.get("reads")?.get(query)?.as_array()
}

/// The request the command claims to touch, as the SERVER sees it (`reads`, ADR-0069).
///
/// whatsapp_inbox#40 — the guard cannot live in the WHERE alone: a `WHERE` that matches nothing
/// still commits, so `requests.fulfill` answered `ok: true` having changed nothing, and
/// `whatsapp_inbox.request.fulfilled` was published for a request nobody handled. And
/// `expect_rows` does not reach a Tier-2 command either: the runtime gate counts rows over the
/// command's own `sql` block, which here is EMPTY (the logic goes through this handler), so the
/// intents arrive as `extra_ops` the gate never counts (ERPlora/tasks#26). The guard goes where
/// there is context: here, before the intent is built.
fn resolve_request_row(input: &Value) -> Result<&Value, DomainError> {
    match read_rows(input, "whatsapp_inbox.requests.get") {
        // Without the read there is no way to know which state the request is in, and guessing is
        // exactly what this guard removes (ADR-0069 §1: a guard that degrades is not a guard).
        None => Err(DomainError::new(
            "whatsapp_inbox.request_unreadable",
            "That request could not be read, so nothing was changed. Try again.",
        )),
        Some(rows) => rows.first().ok_or_else(|| {
            DomainError::new(
                "whatsapp_inbox.request_not_found",
                "That request does not exist in this business.",
            )
        }),
    }
}

/// Lógica pura: `{payload, context}` → intenciones, o error de negocio.
pub fn fulfill_request_pure(input: Value) -> Result<Output, String> {
    let payload = input.get("payload").cloned().unwrap_or(Value::Null);

    let request_id = payload.get("request_id").map(as_str).unwrap_or_default();
    if request_id.is_empty() {
        return Err("invalid_payload: request_id requerido".to_string());
    }

    let create_linked_object = payload
        .get("create_linked_object")
        .map(as_bool)
        .unwrap_or(false);

    if create_linked_object {
        // Rama de dispatch cross-módulo: bloqueada por el aislamiento del
        // runtime (un handler solo puede invocar commands de su propio módulo)
        // y por la falta de lecturas pre-cargadas. Pendiente de decisión de
        // arquitectura — ver WASM-TODO.md §1 y el doc del módulo.
        return Err(
            "cross_module_dispatch_unsupported: el runtime no permite aún que un handler \
             invoque commands de otros módulos (aislamiento §5.3); la request no se ha \
             modificado"
                .to_string(),
        );
    }

    // whatsapp_inbox#40 — only a CONFIRMED request can be marked as handled, and the refusal has
    // to travel as a domain code instead of a silent no-op. The state guard of the WHERE in
    // `_fulfill_transition.sql` stays as the race safety net; this is the answer the caller reads.
    let request = match resolve_request_row(&input) {
        Ok(row) => row,
        Err(e) => return Ok(Output::new().with_error(e)),
    };
    let status = as_str(request.get("status").unwrap_or(&Value::Null));
    if status != "confirmed" {
        return Ok(Output::new().with_error(DomainError::new(
            "whatsapp_inbox.request_not_fulfillable",
            "Only a confirmed request can be marked as handled.",
        )));
    }

    let mut params = Map::new();
    params.insert("request_id".into(), json!(request_id));

    Ok(Output::new().with_operation(Operation::sql(
        "whatsapp_inbox._fulfill_transition",
        params,
    )))
}

// ───────────────────── parse_inbound_message (WASM-TODO §3) ─────────────────────

/// Tipos de request soportados (columna `request_type`); un valor desconocido
/// se normaliza a `custom` (default del esquema legacy).
const REQUEST_TYPES: [&str; 6] = [
    "order",
    "reservation",
    "appointment",
    "quote",
    "transport",
    "custom",
];

/// Valida `parsed_data` contra el `request_schema` dinámico de settings
/// (subconjunto de JSON Schema: `required` + `properties.*.type`). El esquema lo
/// aporta el **caller** en el payload (lectura vía `whatsapp_inbox.settings.get`)
/// porque el runtime no pre-carga lecturas para el guest — validación
/// no-autoritativa, patrón ADR-0021 (appointments); las garantías autoritativas
/// (reference_number, status por approval_mode, guarda de conversación) viven en
/// el SQL de `_bump_request_counter`/`_insert_request`.
fn validate_against_schema(data: &Value, schema: &Value) -> Result<(), String> {
    let Some(schema) = schema.as_object() else {
        return Ok(()); // sin esquema (o `{}` por defecto) → no se valida forma
    };
    if schema.is_empty() {
        return Ok(());
    }
    let mut errors: Vec<String> = Vec::new();
    if let Some(required) = schema.get("required").and_then(|v| v.as_array()) {
        for field in required.iter().filter_map(|f| f.as_str()) {
            let present = data.get(field).map(|v| !v.is_null()).unwrap_or(false);
            if !present {
                errors.push(format!("falta el campo requerido `{field}`"));
            }
        }
    }
    if let Some(props) = schema.get("properties").and_then(|v| v.as_object()) {
        for (field, spec) in props {
            let Some(expected) = spec.get("type").and_then(|t| t.as_str()) else {
                continue;
            };
            let Some(value) = data.get(field) else { continue };
            if value.is_null() {
                continue;
            }
            let ok = match expected {
                "string" => value.is_string(),
                "number" => value.is_number(),
                "integer" => value.as_i64().is_some() || value.as_u64().is_some(),
                "boolean" => value.is_boolean(),
                "array" => value.is_array(),
                "object" => value.is_object(),
                _ => true, // tipo desconocido en el esquema → no bloquear
            };
            if !ok {
                errors.push(format!("`{field}` debería ser {expected}"));
            }
        }
    }
    if errors.is_empty() {
        Ok(())
    } else {
        Err(format!("schema_validation_failed: {}", errors.join("; ")))
    }
}

/// `YYYYMMDD` a partir del `context.now` RFC3339 que inyecta el host.
fn day_from_now(now: &str) -> Result<String, String> {
    if now.len() < 10 || now.as_bytes()[4] != b'-' || now.as_bytes()[7] != b'-' {
        return Err("context.now inválido (lo inyecta el host)".to_string());
    }
    Ok(format!("{}{}{}", &now[0..4], &now[5..7], &now[8..10]))
}

/// Lógica pura de `parse_inbound_message`: `{payload, context}` → intenciones
/// `_bump_request_counter` + `_insert_request`, o error de negocio.
///
/// Payload: `conversation_id` (req.), `parsed_data` (req., objeto JSON ya
/// devuelto por el LLM vía proxy del Cloud §9.3 — el guest NUNCA llama al
/// modelo), `confidence` (0.0–1.0), `request_type` (opcional; si falta se toma
/// de `parsed_data.request_type`; desconocido → `custom`), `raw_summary`
/// (opcional; si falta se toma de `parsed_data.summary`) y `request_schema`
/// (opcional, aportado por el caller desde settings).
pub fn parse_inbound_message_pure(input: Value) -> Result<Output, String> {
    let payload = input.get("payload").cloned().unwrap_or(Value::Null);
    let context = input.get("context").cloned().unwrap_or(Value::Null);

    let conversation_id = payload.get("conversation_id").map(as_str).unwrap_or_default();
    if conversation_id.is_empty() {
        return Err("invalid_payload: conversation_id requerido".to_string());
    }

    let parsed_data = payload.get("parsed_data").cloned().unwrap_or(Value::Null);
    if !parsed_data.is_object() {
        return Err("invalid_payload: parsed_data (objeto JSON del LLM) requerido".to_string());
    }

    // Validación de forma contra el esquema dinámico aportado por el caller.
    if let Some(schema) = payload.get("request_schema") {
        validate_against_schema(&parsed_data, schema)?;
    }

    // whatsapp_inbox#40 — the conversation has to EXIST before an intent that would emit
    // `whatsapp_inbox.request.created` is built. The authoritative guard until now was the
    // INSERT..SELECT of `_insert_request` (0 filas si la conversación no existe), but a Tier-2
    // command has no `sql` block of its own, so nothing weighed that count: a ghost
    // `conversation_id` committed, answered `ok` and published `request.created` for a request
    // that does not exist (the phantom-event shape of #40, one door further in). Same pattern as
    // `fulfill_request`: the state lives in a pre-loaded read (ADR-0069), the refusal is a code.
    match read_rows(&input, "whatsapp_inbox.conversations.get") {
        Some(rows) if !rows.is_empty() => {}
        Some(_) => {
            return Ok(Output::new().with_error(DomainError::new(
                "whatsapp_inbox.conversation_not_found",
                "That conversation does not exist in this business.",
            )))
        }
        None => {
            return Ok(Output::new().with_error(DomainError::new(
                "whatsapp_inbox.conversation_unreadable",
                "That conversation could not be read, so nothing was created. Try again.",
            )))
        }
    }

    // confidence (0.0–1.0) → confidence_score, con clamp defensivo.
    let confidence = payload
        .get("confidence")
        .and_then(|v| v.as_f64())
        .unwrap_or(0.0)
        .clamp(0.0, 1.0);

    // request_type: payload > parsed_data.request_type > 'custom'; desconocido → 'custom'.
    let raw_type = payload
        .get("request_type")
        .map(as_str)
        .filter(|s| !s.is_empty())
        .or_else(|| {
            parsed_data
                .get("request_type")
                .map(as_str)
                .filter(|s| !s.is_empty())
        })
        .unwrap_or_default();
    let request_type = if REQUEST_TYPES.contains(&raw_type.as_str()) {
        raw_type
    } else {
        "custom".to_string()
    };

    let raw_summary = payload
        .get("raw_summary")
        .map(as_str)
        .filter(|s| !s.is_empty())
        .or_else(|| parsed_data.get("summary").map(as_str).filter(|s| !s.is_empty()))
        .unwrap_or_default();

    // Contexto del host: id de la request (autoridad de ids = host) y día YYYYMMDD.
    let request_id = context
        .get("new_ids")
        .and_then(|v| v.as_array())
        .and_then(|a| a.first())
        .map(as_str)
        .filter(|s| !s.is_empty())
        .ok_or_else(|| "context.new_ids vacío (lo inyecta el host)".to_string())?;
    let now = context.get("now").map(as_str).unwrap_or_default();
    let day = day_from_now(&now)?;

    let data_json = serde_json::to_string(&parsed_data)
        .map_err(|e| format!("invalid_payload: parsed_data no serializable ({e})"))?;

    let mut bump = Map::new();
    bump.insert("day".into(), json!(day));

    let mut insert = Map::new();
    insert.insert("request_id".into(), json!(request_id));
    insert.insert("conversation_id".into(), json!(conversation_id));
    insert.insert("day".into(), json!(day));
    insert.insert("request_type".into(), json!(request_type));
    insert.insert("data".into(), json!(data_json));
    insert.insert("raw_summary".into(), json!(raw_summary));
    insert.insert("confidence_score".into(), json!(confidence));

    Ok(Output::new()
        .with_operation(Operation::sql("whatsapp_inbox._bump_request_counter", bump))
        .with_operation(Operation::sql("whatsapp_inbox._insert_request", insert)))
}

// ───────────────────── link_known_customer (whatsapp_inbox#149) ─────────────────────

/// The query whose rows `_link_known_customer` pre-loads (`reads`, ADR-0069). `customers` is a HARD
/// dependency of this module, so the read is in scope; the module still never touches the customers
/// table from its own SQL (`customer_id` stays a soft reference).
const CUSTOMERS_READ: &str = "customers.list";

/// A phone reduced to its digits: `+34 600-111-222` and `34600111222` are the same number.
fn phone_digits(v: &Value) -> String {
    as_str(v).chars().filter(|c| c.is_ascii_digit()).collect()
}

/// The contact the thread is keyed by — the value `wa_contact_id` holds for this message — or
/// `None` when the payload names nobody the business talks to.
///
/// Two emitters publish `whatsapp_inbox.message.received`, each with its own payload:
/// * `_ingest_inbound_message` (the core event): `contact` is the customer in BOTH directions
///   (hub#1612). A hub older than that sends no `contact`, and then `from` is the thread — but only
///   when the customer SPOKE: in an outbound echo `from` is the shop's own number.
/// * `messages.ingest`: `wa_contact_id`, verbatim.
fn thread_contact(payload: &Value) -> Option<String> {
    let field = |k: &str| payload.get(k).map(as_str).filter(|s| !s.is_empty());
    if let Some(contact) = field("contact") {
        return Some(contact);
    }
    if let Some(wa_contact_id) = field("wa_contact_id") {
        return Some(wa_contact_id);
    }
    let direction = field("direction").unwrap_or_else(|| "inbound".to_string());
    if direction == "inbound" {
        return field("from");
    }
    None
}

/// Links the conversation to the customer whose card carries the number that wrote — with NO
/// automation installed (whatsapp_inbox#149). Runs as the listener of this module's own
/// `whatsapp_inbox.message.received`, after the thread row exists.
///
/// It NEVER refuses: a listener that errors is retried and dead-letters, and «we could not tell
/// whose it is» is not a failure of the message. Every doubt resolves to «link nobody»:
/// * the read did not arrive (`None`) — nothing is guessed from an absent catalogue;
/// * the read is a LIKE (`%digits%`), so the handler decides by EXACT digits: a longer number that
///   merely contains the contact is somebody else;
/// * two different customers carry the number — picking one files the thread under the wrong
///   person, so a human decides.
///
/// Whether an EXISTING link is kept is the write's job (`_link_known_customer_write.sql` only fills
/// an empty `customer_id`): a person or a recipe that already linked the thread wins.
pub fn link_known_customer_pure(input: Value) -> Result<Output, String> {
    let payload = input.get("payload").cloned().unwrap_or(Value::Null);
    let Some(contact) = thread_contact(&payload) else {
        return Ok(Output::new());
    };
    let wanted = phone_digits(&Value::String(contact.clone()));
    if wanted.is_empty() {
        return Ok(Output::new());
    }
    let Some(rows) = read_rows(&input, CUSTOMERS_READ) else {
        return Ok(Output::new());
    };

    let mut matches: Vec<String> = rows
        .iter()
        .filter(|row| phone_digits(row.get("phone").unwrap_or(&Value::Null)) == wanted)
        .map(|row| as_str(row.get("id").unwrap_or(&Value::Null)))
        .filter(|id| !id.is_empty())
        .collect();
    matches.sort();
    matches.dedup();
    let [customer_id] = matches.as_slice() else {
        return Ok(Output::new());
    };

    let mut params = Map::new();
    params.insert("wa_contact_id".into(), json!(contact));
    params.insert("customer_id".into(), json!(customer_id));
    Ok(Output::new().with_operation(Operation::sql(
        "whatsapp_inbox._link_known_customer_write",
        params,
    )))
}

// ───────────────────── tests (pure functions, no DB, ADR-0069 §1) ─────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn request_row(status: &str) -> Value {
        json!({
            "id": "r1",
            "reference_number": "WA-20260822-0001",
            "request_type": "reservation",
            "status": status,
            "contact_name": "Ana",
        })
    }

    fn conversation_row() -> Value {
        json!({ "id": "c1", "contact_name": "Ana", "contact_phone": "+34600111222" })
    }

    /// `reads` arrive as `{query: [rows]}` under `context.reads` — the host's half of ADR-0069.
    fn input_with(payload: Value, reads: Value) -> Value {
        json!({ "payload": payload, "context": { "reads": reads, "now": "2026-08-22T09:00:00+00:00", "new_ids": ["n1"] } })
    }

    // ── fulfill_request: the state guard the WHERE alone could not give (whatsapp_inbox#40) ──

    #[test]
    fn fulfill_on_a_confirmed_request_builds_the_transition_intent() {
        let input = input_with(
            json!({ "request_id": "r1" }),
            json!({ "whatsapp_inbox.requests.get": [request_row("confirmed")] }),
        );
        let out = fulfill_request_pure(input).expect("the happy path must not fail");
        assert!(out.error.is_none(), "no refusal expected: {out:?}");
        assert_eq!(out.operations.len(), 1);
        assert_eq!(out.operations[0].command, "whatsapp_inbox._fulfill_transition");
    }

    #[test]
    fn fulfill_on_a_pending_request_refuses_with_a_domain_error_and_no_operations() {
        let input = input_with(
            json!({ "request_id": "r1" }),
            json!({ "whatsapp_inbox.requests.get": [request_row("pending_review")] }),
        );
        let out = fulfill_request_pure(input).expect("a refusal is an output, not a trap");
        let error = out.error.expect("a pending request must be refused");
        assert_eq!(error.code, "whatsapp_inbox.request_not_fulfillable");
        assert!(
            out.operations.is_empty(),
            "a refusal must carry no intent: the host would execute it"
        );
    }

    #[test]
    fn fulfill_on_an_unknown_request_says_not_found() {
        let input = input_with(
            json!({ "request_id": "r-ghost" }),
            json!({ "whatsapp_inbox.requests.get": [] }),
        );
        let out = fulfill_request_pure(input).expect("a refusal is an output, not a trap");
        assert_eq!(out.error.expect("an empty read must refuse").code, "whatsapp_inbox.request_not_found");
        assert!(out.operations.is_empty());
    }

    #[test]
    fn fulfill_without_the_read_refuses_instead_of_guessing() {
        // ADR-0069 §1: a guard that degrades is not a guard. No read → no way to know the state
        // → refuse loudly, never fall back to "probably fine".
        let input = input_with(json!({ "request_id": "r1" }), json!({}));
        let out = fulfill_request_pure(input).expect("a refusal is an output, not a trap");
        assert_eq!(out.error.expect("a missing read must refuse").code, "whatsapp_inbox.request_unreadable");
        assert!(out.operations.is_empty());
    }

    #[test]
    fn fulfill_still_refuses_the_cross_module_branch_before_anything_else() {
        let input = input_with(
            json!({ "request_id": "r1", "create_linked_object": true }),
            json!({ "whatsapp_inbox.requests.get": [request_row("confirmed")] }),
        );
        assert!(fulfill_request_pure(input).is_err());
    }

    // ── parse_inbound_message: the conversation must exist BEFORE a phantom request.created ──

    #[test]
    fn parse_with_a_live_conversation_builds_both_intents() {
        let input = input_with(
            json!({
                "conversation_id": "c1",
                "parsed_data": { "service": "tinte", "when": "mañana a las 10" },
                "confidence": 0.8,
            }),
            json!({ "whatsapp_inbox.conversations.get": [conversation_row()] }),
        );
        let out = parse_inbound_message_pure(input).expect("the happy path must not fail");
        assert!(out.error.is_none(), "no refusal expected: {out:?}");
        assert_eq!(out.operations.len(), 2);
        assert_eq!(out.operations[0].command, "whatsapp_inbox._bump_request_counter");
        assert_eq!(out.operations[1].command, "whatsapp_inbox._insert_request");
    }

    #[test]
    fn parse_for_a_conversation_that_does_not_exist_refuses_with_no_intents() {
        // Without this guard the INSERT..SELECT of `_insert_request` writes 0 rows, the host
        // commits, and `whatsapp_inbox.request.created` is published for a request that does
        // not exist — the phantom-event shape of whatsapp_inbox#40, one door further in.
        let input = input_with(
            json!({
                "conversation_id": "c-ghost",
                "parsed_data": { "service": "tinte" },
            }),
            json!({ "whatsapp_inbox.conversations.get": [] }),
        );
        let out = parse_inbound_message_pure(input).expect("a refusal is an output, not a trap");
        let error = out.error.expect("a ghost conversation must be refused");
        assert_eq!(error.code, "whatsapp_inbox.conversation_not_found");
        assert!(out.operations.is_empty());
    }

    #[test]
    fn parse_without_the_read_still_validates_the_payload_shape_first() {
        // Payload validation is payload validation; the read guard answers a different question.
        let input = input_with(json!({ "conversation_id": "c1" }), json!({}));
        assert!(
            parse_inbound_message_pure(input).is_err(),
            "a missing parsed_data must stay a payload error, not a read refusal"
        );
    }

    // ── link_known_customer: the thread learns whose it is with NO automation (whatsapp_inbox#149) ──

    fn customer(id: &str, phone: &str) -> Value {
        json!({ "id": id, "name": "Ana", "phone": phone })
    }

    fn core_event(contact: &str) -> Value {
        json!({ "wa_message_id": "wamid.1", "from": contact, "contact": contact, "direction": "inbound", "text": "hola" })
    }

    fn linked(out: &Output) -> (String, String) {
        assert!(out.error.is_none(), "a listener must never refuse: {out:?}");
        assert_eq!(out.operations.len(), 1, "exactly one link intent expected: {out:?}");
        let op = &out.operations[0];
        assert_eq!(op.command, "whatsapp_inbox._link_known_customer_write");
        (as_str(&op.params["wa_contact_id"]), as_str(&op.params["customer_id"]))
    }

    fn untouched(out: &Output) {
        assert!(out.error.is_none(), "a listener must never refuse (it would dead-letter the message): {out:?}");
        assert!(out.operations.is_empty(), "nothing may be linked here: {out:?}");
    }

    #[test]
    fn a_message_from_a_number_on_file_links_the_thread_to_that_customer() {
        let input = input_with(
            core_event("34600111222"),
            json!({ "customers.list": [customer("cu-ana", "+34600111222")] }),
        );
        let out = link_known_customer_pure(input).expect("no trap");
        assert_eq!(linked(&out), ("34600111222".to_string(), "cu-ana".to_string()));
    }

    #[test]
    fn the_phone_on_file_matches_whatever_way_it_was_typed() {
        // The read filters with LIKE, the handler decides by DIGITS: spaces, dashes and the `+`
        // the owner typed on the customer card are formatting, not a different number.
        let input = input_with(
            core_event("34600111222"),
            json!({ "customers.list": [customer("cu-ana", "+34 600-111-222")] }),
        );
        assert_eq!(linked(&link_known_customer_pure(input).unwrap()).1, "cu-ana");
    }

    #[test]
    fn a_longer_number_that_merely_contains_the_contact_is_not_her() {
        // LIKE '%34600111222%' also answers +346001112229: containing is not being.
        let input = input_with(
            core_event("34600111222"),
            json!({ "customers.list": [customer("cu-other", "+346001112229")] }),
        );
        untouched(&link_known_customer_pure(input).unwrap());
    }

    #[test]
    fn two_different_customers_with_that_number_link_nobody() {
        // Two cards, one phone (a mother and her daughter share it): picking one would file the
        // thread under the wrong person. Leave it for a human.
        let input = input_with(
            core_event("34600111222"),
            json!({ "customers.list": [customer("cu-ana", "+34600111222"), customer("cu-eva", "34600111222")] }),
        );
        untouched(&link_known_customer_pure(input).unwrap());
    }

    #[test]
    fn a_number_nobody_has_on_file_links_nobody_and_does_not_fail() {
        let input = input_with(core_event("34600111222"), json!({ "customers.list": [] }));
        untouched(&link_known_customer_pure(input).unwrap());
    }

    #[test]
    fn without_the_read_nothing_is_guessed_and_the_message_is_not_dead_lettered() {
        let input = input_with(core_event("34600111222"), json!({}));
        untouched(&link_known_customer_pure(input).unwrap());
    }

    #[test]
    fn the_echo_of_the_owners_reply_links_the_customer_not_the_shop() {
        // hub#1612: in an echo `from` is the shop's own number; `contact` is still the customer.
        let payload = json!({ "wa_message_id": "wamid.2", "from": "34911000000", "contact": "34600111222", "direction": "outbound" });
        let input = input_with(
            payload,
            json!({ "customers.list": [customer("cu-shop", "+34911000000"), customer("cu-ana", "+34600111222")] }),
        );
        assert_eq!(linked(&link_known_customer_pure(input).unwrap()), ("34600111222".to_string(), "cu-ana".to_string()));
    }

    #[test]
    fn a_hub_older_than_the_contact_field_falls_back_to_the_sender() {
        let payload = json!({ "wa_message_id": "wamid.3", "from": "34600111222" });
        let input = input_with(payload, json!({ "customers.list": [customer("cu-ana", "+34600111222")] }));
        assert_eq!(linked(&link_known_customer_pure(input).unwrap()), ("34600111222".to_string(), "cu-ana".to_string()));
    }

    #[test]
    fn a_hub_older_than_the_contact_field_never_links_an_echo_to_the_shop() {
        // No `contact` and an outbound echo: `from` is the SHOP, so there is nobody to link.
        let payload = json!({ "wa_message_id": "wamid.4", "from": "34911000000", "direction": "outbound" });
        let input = input_with(payload, json!({ "customers.list": [customer("cu-shop", "+34911000000")] }));
        untouched(&link_known_customer_pure(input).unwrap());
    }

    #[test]
    fn the_manual_ingest_door_is_keyed_by_its_own_contact_fields() {
        // `messages.ingest` emits the same event with ITS payload: `wa_contact_id` + `contact_phone`.
        let payload = json!({ "wa_contact_id": "34600111222", "contact_phone": "+34600111222", "wa_message_id": "wamid.5" });
        let input = input_with(payload, json!({ "customers.list": [customer("cu-ana", "+34600111222")] }));
        assert_eq!(linked(&link_known_customer_pure(input).unwrap()), ("34600111222".to_string(), "cu-ana".to_string()));
    }

    #[test]
    fn a_customer_card_without_a_phone_is_never_a_match() {
        let input = input_with(core_event("34600111222"), json!({ "customers.list": [customer("cu-x", ""), json!({"id": "cu-y"})] }));
        untouched(&link_known_customer_pure(input).unwrap());
    }
}

//! Handler WASM (Tier 2) del módulo `whatsapp_inbox`.
//! Lógica pura, sin BD: recibe `{payload, context}` y devuelve **intenciones**
//! (operaciones SQL del propio módulo) que el host valida y ejecuta en una
//! transacción. Los eventos los emite el runtime vía el `emit` declarado en
//! `module.json` (no se duplican aquí).
//!
//! Exporta dos funciones:
//! * `fulfill_request` — cumplir una request (portado de
//!   `RequestService.fulfill_request`, ver `WASM-TODO.md` §1).
//! * `parse_inbound_message` — crear la request parseada por el LLM (pieza 3 de
//!   `WASM-TODO.md`; la persistencia del mensaje inbound la cubre el command
//!   Tier-0 `whatsapp_inbox.messages.ingest`).
//!
//! Ramas:
//! * `create_linked_object = false` (default) — transición simple a `fulfilled`.
//!   La guarda de estado (**solo** desde `confirmed`) vive en el WHERE de
//!   `commands/_fulfill_transition.sql`, igual que en `approve`/`reject`: el
//!   runtime no pre-carga lecturas para el guest, así que el estado actual no
//!   es visible aquí y la autoridad es siempre el SQL (0 filas afectadas si la
//!   request no está `confirmed` — equivalente al `invalid_status` legacy).
//! * `create_linked_object = true` — dispatch cross-módulo (crear el objeto en
//!   el módulo destino vía su command público y enlazar `linked_module`/
//!   `linked_object_id`). **NO soportado todavía**: el runtime rechaza
//!   operaciones de handlers sobre commands de otros módulos
//!   (`validate_operation`, aislamiento ARQUITECTURA.md §5.3) y no existe la
//!   capacidad de lecturas pre-cargadas (settings.`output_modules`, request).
//!   Hasta que esa decisión de modelo de comandos se tome (issue #3/#5), esta
//!   rama devuelve el error explícito `cross_module_dispatch_unsupported`.

use erplora_guest_sdk::{Operation, Output};
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

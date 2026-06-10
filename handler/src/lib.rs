//! Handler WASM (Tier 2) del módulo `whatsapp_inbox` — cumplir una request.
//! Portado de `RequestService.fulfill_request` (ver `WASM-TODO.md` §1). Lógica
//! pura, sin BD: recibe `{payload, context}` y devuelve **intenciones**
//! (operaciones SQL del propio módulo) que el host valida y ejecuta en una
//! transacción. El evento `whatsapp_inbox.request.fulfilled` lo emite el runtime
//! vía el `emit` declarado en `module.json` (no se duplica aquí).
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

# whatsapp_inbox — lógica para handler Rust→WASM (Tier 2)

> ## ⚠️ Revisión 2026-08-11 (pm#112): el kernel de flujos existe, y tres piezas de esta lista SOBRAN
>
> Esta lista se escribió cuando el hub no tenía **kernel de automatización**. Con ADR-0283
> implementado (triggers, grants, executor, step `http`, step `ai` con bandeja de aprobación, step
> `notify` con grant `recipient_query`), el reparto cambió: **el producto son flujos, no un handler
> WASM que reimplemente medio motor dentro de un módulo.** Lo que este módulo aporta al caso
> estrella ya está entero y es una línea de manifest:
>
> ```json
> "events": { "listen": { "hub.whatsapp.message_received": { "command": "whatsapp_inbox._ingest_inbound_message" } } }
> ```
>
> Decisiones tomadas (y por qué), pieza por pieza:
>
> | Pieza | Decisión | Por qué |
> | --- | --- | --- |
> | **§1 dispatch cross-módulo** de `fulfill_request` | ❌ **DESCARTADA** | No está «bloqueada por el runtime»: está **prohibida a propósito** y esa prohibición se reforzó (hub#659, ADR-0283 §7). Reaccionar ejecutando el command de otro módulo es territorio de un **flujo con grant explícito**, que además es auditable y revocable — un handler que lo hiciera sería una capacidad sin dueño. `whatsapp_inbox#3` deja de tener sentido como issue de este módulo. |
> | **§4 `build_catalog_context` / `build_output_context`** | ❌ **DESCARTADA** | El step `ai` ya ofrece al modelo las **tools reales** del hub (`assemble_tools` ∩ lo que declara el step ∩ los grants vivos) y es el modelo quien decide qué leer. Precocinar un bloque de texto con los `input_modules` configurados es estrictamente peor: no puede contestar a lo que el modelo pregunte, y el guest **no tiene lecturas pre-cargadas** (ADR-0069 nunca se implementó). |
> | **§5 `auto_reply`** | ❌ **DESCARTADA** | El step `notify` (hub#821) escribe al cliente por el **outbox**, con reintentos, backoff y dead-letter, y por el proxy del SaaS. La versión WASM exigía `http.fetch` a la Graph API **con credenciales de Meta en el hub**, que es justo lo que la arquitectura prohíbe (§9.3: el hub nunca guarda credenciales de Meta/SES). No era una pieza pendiente: era una pieza imposible. |
> | **§6 `configure` por caso de uso** | ❌ **DESCARTADA** | Lo que hacía (elegir módulos de entrada/salida, esquema y prompt **por vertical**) es exactamente lo que hoy es una **plantilla de flujo** distribuida con el blueprint del sector. Mantener las dos sería tener dos fuentes de verdad para «cómo se comporta el bot de esta peluquería», y solo una de ellas se puede editar, versionar y revocar. |
> | §2 contador atómico | ✅ implementada (ADR-0008) | — |
> | §3 `parse_inbound_message` | ✅ implementada, **fuera del camino del caso estrella** | Sigue siendo el pipeline de `whatsapp_inbox_request`. La cita que reserva la IA **no** pasa por ahí: la escribe el flujo en el turno, por la puerta del dispatcher (`Origin::Automation`), que es la que chequea el grant y su `payload` fijado. Desde whatsapp_inbox#124 ninguna receta viva aparca nada en `_flow_approvals`. |
> | §7 `sync_with_meta`, §8 per-empleado | ⏸ sin cambios | Ni bloquean el caso estrella ni los toca el kernel. |
>
> **Columnas de settings que quedaron sin dueño** (`input_modules`, `output_modules`,
> `gpt_system_prompt`, `auto_reply_enabled`, `greeting_message`, `out_of_hours_message`,
> `require_confirmation`, `auto_close_hours`, y también `is_enabled`, `account_mode`,
> `notify_staff_new_request`, `request_schema`): **retiradas en whatsapp_inbox#127** con la
> migración `contract` 012 (apartadas a `_deprecated_*`, no borradas), junto con `settings.get` /
> `settings.upsert`, que no tenían llamador. Su contenido lo dice ahora el **documento del flujo**
> (el prompt, el texto de la respuesta inmediata, qué tools se ofrecen), que además el dueño puede
> editar sin republicar el módulo.

El CRUD plano (plantillas, settings, asignación de conversación) y las transiciones de
estado simples con guarda (`approve`/`reject`/`delete` de requests) ya están en SQL
declarativo Tier 0 (`commands/*.sql`). Lo que sigue es lógica de IA / dispatch
cross-módulo / numeración atómica / esquema dinámico que **no** cabe en una sola
sentencia SQL y debe convertirse en handler WASM (`handler/src/lib.rs` → `dist/handler.wasm`).

> Regla hub: el WASM **nunca toca la BD**. Recibe el payload + datos leídos por el
> runtime (queries internas), calcula y devuelve *intenciones* (filas a insertar/actualizar,
> comandos a ejecutar, eventos a emitir) que el runtime valida y persiste en una transacción.
> **Cross-módulo = contratos, no imports.** El legacy `INPUT_MODULE_REGISTRY` /
> `OUTPUT_MODULE_REGISTRY` hacían SELECT directo a tablas de otros módulos (catalog,
> inventory, services, reservations, kitchen_orders…). En hub eso está **prohibido**:
> debe pasar por queries/commands públicos namespaced (`inventory.products.list`,
> `reservations.reservation.create`, …) o por eventos de dominio.

---

## 1. `fulfill_request` (command `whatsapp_inbox.requests.fulfill`) — handler COMPILADO (`handler/src/lib.rs` → `dist/handler.wasm`); rama simple operativa, rama de dispatch PENDIENTE de runtime
Origen: `RequestService.fulfill_request` + `actions.execute_action`.

> Estado 2026-06-10: la rama `create_linked_object=false` está implementada (intención
> `whatsapp_inbox._fulfill_transition`, guarda `confirmed`→`fulfilled` en el WHERE). La rama
> `create_linked_object=true` devuelve el error `cross_module_dispatch_unsupported`: el
> runtime actual **rechaza** operaciones de un handler sobre commands de otros módulos
> (`validate_operation`, aislamiento ARQUITECTURA.md §5.3) y no existe aún la capacidad de
> lecturas pre-cargadas (settings/request). Desbloquear el dispatch = decisión de modelo de
> comandos — delegable a la IA con TDD + documentar en `architecture/` + decision-log (división
> de labor humano/IA derogada, ERPlora/pm#43), ver issue whatsapp_inbox#3.
- Guarda de estado: **solo** desde `confirmed` (si no → error `invalid_status`).
- Si `create_linked_object = false`: solo transicionar la request a `fulfilled`
 (`status='fulfilled'`, `fulfilled_at = now`). Esto NO necesita WASM por sí solo, pero
 comparte command con la rama de dispatch, así que el handler resuelve ambas ramas.
- Si `create_linked_object = true` → **dispatch cross-módulo**:
 1. Mapear `request_type` → módulo destino vía `output_modules` de settings
 (registro: order→sales/kitchen_orders, reservation→reservations/tables,
 appointment→appointments, quote→quotes, transport→carriers/delivery…). El mapa
 legacy `OUTPUT_MODULE_REGISTRY` se traduce a una tabla de despacho declarada en el
 manifest/handler (NO a imports).
 2. Comprobar disponibilidad llamando a una **query pública** del módulo destino
 (equivalente al `check_availability(hub_id, data)` legacy). Si no disponible →
 anotar `data._alternatives` / `data._unavailable_reason` (intención de UPDATE sobre
 `whatsapp_inbox_request.data`) y devolver `{status:'unavailable', alternatives:[...]}`
 sin transicionar.
 3. Crear el objeto destino emitiendo el **command público** correspondiente
 (p.ej. `reservations.reservation.create`, `quotes.quotes.create`) con el payload
 construido desde `request.data`. El runtime ejecuta ese command (cross-módulo) y
 devuelve el `id` del objeto creado.
 4. Persistir el enlace en la request: `linked_module = <module_id>`,
 `linked_object_id = <id devuelto>`, `status='fulfilled'`, `fulfilled_at = now`.
 5. Emitir `whatsapp_inbox.request.fulfilled` con `{request_id, reference_number,
 request_type, linked_module, linked_object_id}`. El módulo destino **no** se importa:
 se invoca por contrato (command público) o se le notifica por evento.
- **Regla de borrado relacionada** (ya en `request_delete.sql`): una request `fulfilled`
 no se puede soft-deletear (la cadena de auditoría hacia el objeto enlazado debe sobrevivir).

## 2. Generación atómica de `reference_number` — IMPLEMENTADO (2026-06-11, ADR-0008)
Origen: las requests legacy llevan `reference_number` único por hub, indexado.
- Debe ser atómico (sin ventana SELECT→UPDATE) en SQLite y Postgres.
- **Resuelto module-side** (ADR-0008: el contador NO es capacidad de runtime compartida;
 mismo patrón que `sales_sale_counter` / `appointments_appointment_counter`):
 tabla `whatsapp_inbox_request_counter` (migración `003_request_counter.sql`, único
 `(hub_id, day)`) + command interno `_bump_request_counter.sql` (UPSERT +1) como primera
 intención del handler; `_insert_request.sql` lee el contador por subquery en la MISMA
 transacción y formatea `'WA-' || :day || '-' || printf('%04d', last_number)`
 (4 dígitos secuenciales por hub+día; `printf()` es SQLite → Postgres usará `lpad()`).

## 3. Parseo de IA del mensaje entrante → `InboxRequest` (`parse_inbound_message`) — IMPLEMENTADO (2026-06-11)
Origen: `bot.build_system_prompt` + `parsed_data`/`confidence` del response de GPT.
- hub **NUNCA habla con LLMs directamente** (§9.3): la llamada al modelo va por el
 proxy del Cloud Portal (metered). El handler WASM recibe el **JSON ya devuelto por el
 modelo** en el payload del command, no llama al LLM él mismo.
- Command público `whatsapp_inbox.requests.ingest` (permiso `manage_connections`, mismo
 caller que `messages.ingest`: el pipeline del webhook) → handler `parse_inbound_message`
 (`handler/src/lib.rs`), emite `whatsapp_inbox.request.created`:
 - Valida `parsed_data` contra el `request_schema` dinámico **aportado por el caller** en
 el payload (subconjunto JSON Schema: `required` + `properties.*.type`) — el runtime no
 pre-carga lecturas para el guest, así que la validación de forma es no-autoritativa
 (patrón ADR-0021/appointments); error `schema_validation_failed` si no cumple.
 - Mapea `confidence` (0.0–1.0, clamp) a `confidence_score`.
 - Decide `request_type` (payload > `parsed_data.request_type` > `custom`; desconocido →
 `custom`) y `raw_summary` (payload > `parsed_data.summary`).
 - Devuelve las intenciones `_bump_request_counter` + `_insert_request` (id de
 `context.new_ids`). Las garantías **autoritativas** viven en el SQL de
 `_insert_request`: `reference_number` (pieza 2), `status` decidido por subquery sobre
 `whatsapp_inbox_settings.approval_mode` (`auto`→`confirmed` + `confirmed_at`; `manual`
 o sin settings→`pending_review`), `customer_id` heredado de la conversación y guarda
 de conversación viva del hub (0 filas si no existe).
 - La parte de mensaje inbound + conversación la cubre el command Tier-0
 `whatsapp_inbox.messages.ingest` (no se duplica aquí).
- Los `DEFAULT_SCHEMAS` legacy (order/reservation/appointment/quote) pertenecen a la pieza
 6 (`configure` por caso de uso), que los sembrará en `settings.request_schema`.

## 4. Construcción de contexto del bot (`build_catalog_context` / `build_output_context`)
Origen: `bot.INPUT_MODULE_REGISTRY` + `build_catalog_context_async` + `build_output_context`.
- El legacy hace SELECT directo a tablas de otros módulos para alimentar el prompt de GPT
 (catálogo de productos, servicios, disponibilidad). **PROHIBIDO en hub.**
- En su lugar, el handler pide al runtime ejecutar **queries públicas** de los `input_modules`
 configurados (p.ej. `inventory.products.list`, `services.services.list`) y compone el
 bloque de texto de contexto a partir de los resultados. El WASM solo formatea texto;
 el runtime es quien lee la BD (de cada módulo, respetando permisos).

## 5. Auto-respuesta y flujo de confirmación (`auto_reply`)
Origen: `bot.py` (confirmation flow) + `WhatsAppInboxSettings.auto_reply_enabled` /
`require_confirmation` / `greeting_message` / `out_of_hours_message` / `auto_close_hours`.
- Cuando `auto_reply_enabled`: el handler compone el texto de respuesta (saludo, fuera de
 horario, confirmación de datos parseados) — texto generado vía proxy del Cloud (§9.3) —
 y devuelve la intención de INSERT de un `WhatsAppMessage` outbound + el efecto de envío
 (capacidad host `http.fetch` mediada → Graph API de Meta, Tier 1).
- `require_confirmation`: si está activo, antes de fijar la request se pide confirmación al
 contacto; el estado del flujo se guarda en `whatsapp_inbox_conversation.context` (JSON).

## 6. `configure` por caso de uso (use-case blueprints)
Origen: `SettingsService.configure` + `_USE_CASE_BLUEPRINTS` + `_assess_use_case` +
`_select_configured_modules` + `_enable_module_on_disk`.
- Toma un `use_case` (restaurant|sales|appointments|quotes) y aplica un blueprint:
 `input_modules`, `output_modules`, `request_schema`, `approval_mode`, `account_mode`,
 `gpt_system_prompt` por defecto.
- Lógica de evaluación (qué módulos faltan / requieren activación / no soportan el handler)
 y la activación de módulos en disco son responsabilidad del **runtime / Cloud marketplace**
 en hub (los módulos ya no se activan moviendo carpetas en disco; se instalan vía
 marketplace). El handler WASM se limita a:
 - Validar el `use_case`.
 - Construir el `gpt_system_prompt` final (`business_info` + prompt por defecto del blueprint).
 - Devolver la intención de upsert de settings (delegada al command Tier-0
 `whatsapp_inbox.settings.upsert`) con los campos del blueprint.
- La comprobación de disponibilidad/entitlement de los módulos destino se hace contra el
 runtime (lista de módulos activos del hub), no leyendo el sistema de ficheros.

## 7. `sync_with_meta` (Tier 1 — placeholder, no bloqueante)
Origen: `WhatsAppTemplateService.sync_with_meta` (hoy `not_implemented`).
- Llamará a la Graph API de Meta (`GET /{waba_id}/message_templates`) vía capacidad host
 `http.fetch` mediada por el runtime (Tier 1), y devolverá las intenciones de UPDATE de
 `meta_status` / `meta_template_id` por plantilla. No implementado en el legacy → queda
 documentado para cuando se aborde la integración real con Meta.

## 8. Modo per-empleado (`EmployeeWhatsAppLink`)
Origen: modelo `EmployeeWhatsAppLink` + `account_mode='per_employee'` en list_conversations.
- La tabla `whatsapp_inbox_employee_link` está creada en la migración pero su gestión
 (alta/baja de vínculo empleado↔número, routing del webhook entrante al empleado dueño del
 `phone_number_id`) no tiene aún command/UI declarativos. Cuando se implemente el routing
 por número, el WASM resolverá `phone_number_id → employee_id` y fijará `assigned_to_id`
 en la conversación al crearla. El filtrado por empleado en el listado ya está soportado en
 `conversations_list.sql` vía el bind `:assigned_to_id` (lo pasa el SDK según el modo).

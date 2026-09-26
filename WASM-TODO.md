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
> | **§1 dispatch cross-módulo** de `fulfill_request` (retirado entero en whatsapp_inbox#206) | ❌ **DESCARTADA** | No está «bloqueada por el runtime»: está **prohibida a propósito** y esa prohibición se reforzó (hub#659, ADR-0283 §7). Reaccionar ejecutando el command de otro módulo es territorio de un **flujo con grant explícito**, que además es auditable y revocable — un handler que lo hiciera sería una capacidad sin dueño. `whatsapp_inbox#3` deja de tener sentido como issue de este módulo. |
> | **§4 `build_catalog_context` / `build_output_context`** | ❌ **DESCARTADA** | El step `ai` ya ofrece al modelo las **tools reales** del hub (`assemble_tools` ∩ lo que declara el step ∩ los grants vivos) y es el modelo quien decide qué leer. Precocinar un bloque de texto con los `input_modules` configurados es estrictamente peor: no puede contestar a lo que el modelo pregunte, y el guest **no tiene lecturas pre-cargadas** (ADR-0069 nunca se implementó). |
> | **§5 `auto_reply`** | ❌ **DESCARTADA** | El step `notify` (hub#821) escribe al cliente por el **outbox**, con reintentos, backoff y dead-letter, y por el proxy del SaaS. La versión WASM exigía `http.fetch` a la Graph API **con credenciales de Meta en el hub**, que es justo lo que la arquitectura prohíbe (§9.3: el hub nunca guarda credenciales de Meta/SES). No era una pieza pendiente: era una pieza imposible. |
> | **§6 `configure` por caso de uso** | ❌ **DESCARTADA** | Lo que hacía (elegir módulos de entrada/salida, esquema y prompt **por vertical**) es exactamente lo que hoy es una **plantilla de flujo** distribuida con el blueprint del sector. Mantener las dos sería tener dos fuentes de verdad para «cómo se comporta el bot de esta peluquería», y solo una de ellas se puede editar, versionar y revocar. |
> | §2 contador atómico | 🪦 retirada en whatsapp_inbox#206 | Solo numeraba solicitudes, y el pipeline de solicitudes salió entero. |
> | §3 `parse_inbound_message` | 🪦 retirada en whatsapp_inbox#206 | Era el pipeline de `whatsapp_inbox_request`, y nadie lo llamaba. La cita que reserva la IA **no** pasa por ahí: la escribe el flujo en el turno, por la puerta del dispatcher (`Origin::Automation`), que es la que chequea el grant y su `payload` fijado. Desde whatsapp_inbox#124 ninguna receta viva aparca nada en `_flow_approvals`. |
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

El CRUD plano (plantillas, asignación de conversación) ya está en SQL declarativo Tier 0
(`commands/*.sql`). Lo que sigue es lógica de IA / dispatch
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

## 1–3. `fulfill_request`, contador de `reference_number` y `parse_inbound_message` — RETIRADAS (whatsapp_inbox#206)

Las tres piezas eran el pipeline de solicitudes (`whatsapp_inbox_request`): cumplir una request,
numerarla `WA-YYYYMMDD-NNNN` con un contador atómico por día y crearla a partir del parseo de la IA.
Nada las alimentaba — ninguna receta llamó nunca a `requests.ingest`, las recetas reservan directas
en Citas y Reservas, y una reserva pendiente de revisar se confirma en Citas—, así que la pestaña se
retiró en whatsapp_inbox#193 y el resto en whatsapp_inbox#206: los dos exports del handler, los
`requests.*`, sus commands internos, permisos, eventos, el listener de
`appointments.booking_request.*`, y la migración `contract` 013 aparta las tablas
`whatsapp_inbox_request` / `whatsapp_inbox_request_counter` y la columna `approval_mode` a
`_deprecated_*` (no se borra ninguna fila). La mitad de Citas (el listener de
`whatsapp_inbox.request.approved`) sale en ERPlora/appointments#183.

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
 `input_modules`, `output_modules`, `request_schema`, `approval_mode` (retirada en #206), `account_mode`,
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

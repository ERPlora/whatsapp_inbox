# Módulo `whatsapp_inbox` — bandeja de WhatsApp y peticiones

Bandeja compartida de un canal de WhatsApp Business: **conversaciones** por contacto con sus
**mensajes**, **peticiones** estructuradas extraídas de la conversación (pedido, reserva, cita,
presupuesto…) con su flujo de revisión, **plantillas** aprobadas por Meta y la configuración del
canal.

> 🔴 **Lo que NO funciona, y hay que saberlo antes de venderlo:**
>
> - **Cumplir una petición NO crea nada en otro módulo** — es el propósito central del módulo y está
>   **bloqueado**: el runtime prohíbe que el handler de un módulo escriba en otro, así que la rama de
>   dispatch devuelve `cross_module_dispatch_unsupported` y lo único que ocurre es el cambio de
>   estado a `fulfilled`.
> - **No se puede ENVIAR un mensaje desde el módulo**: no hay command de envío y el manifest no
>   declara `capabilities`, así que el runtime tampoco llegaría a Meta. Quien contesta es el paso
>   **`notify`** de un flujo (hub#821), por el outbox y el proxy del SaaS — donde viven las
>   credenciales. El permiso `send_message` se **retiró** en whatsapp_inbox#29: no gateaba nada.
> - **No hay pantalla de ajustes del canal** (whatsapp_inbox#6).
> - **Las auto-respuestas se configuran y no se envían.** Las plantillas guardan su estado en Meta y
>   **nadie lo sincroniza**.
>
> ✅ **Lo que SÍ funciona y antes no**: los mensajes entran solos (evento core
> `hub.whatsapp.message_received`, [#27](https://github.com/ERPlora/whatsapp_inbox/pull/27)) y
> **exactamente una vez** (índice único parcial sobre `(hub_id, wa_message_id)`,
> whatsapp_inbox#30); y la conversación **se abre y se lee** desde la bandeja
> (whatsapp_inbox#29).

<!-- -->

> **Module id:** `whatsapp_inbox`. **Depende de:** `customers` (referencia blanda, por queries
> públicas, sin FK). Módulo híbrido: SQL + handler WASM **parcial**
> (`fulfill_request`, `parse_inbound_message`).
> ⚠️ Su doc de arquitectura sigue en `architecture/_frozen/modules/whatsapp_inbox.md` — el módulo
> salió de `_frozen/` (pm#112, ADR-0283) pero el `.md` no se ha movido todavía.

## Documentación de usuario — [`docs/`](docs/)

Viaja **dentro** del módulo y se versiona con él: el asistente del hub (ADR-0282) la indexa por
versión instalada y cita la de TU versión, no la de la última publicada. En inglés (idioma fuente).

| Fichero | Para qué |
| ------- | -------- |
| [`docs/overview.md`](docs/overview.md) | Qué hace, qué NO hace y **la limitación central** |
| [`docs/screens.md`](docs/screens.md) | Inbox / Requests / Templates y los ajustes del canal |
| [`docs/concepts.md`](docs/concepts.md) | Cumplir **no crea nada**, no hay envío, el `request_schema` lo aporta el CALLER (no autoritativo), tipo desconocido → `custom`, permisos **muy** admin |
| [`docs/limits.md`](docs/limits.md) | Tabla de qué funciona y qué no, permisos por acción y diagnóstico |

## Permisos: muy cargados hacia admin

| Rol | Puede |
| --- | ----- |
| `admin` | todo |
| `manager` | ver conversaciones y peticiones; **aprobar/rechazar/cumplir**. **No** puede asignar conversación, **ni ver plantillas**, **ni** ver/guardar ajustes, ni ingerir, ni borrar |
| `employee` | solo leer conversaciones y peticiones |

⚠️ `send_message` **ya no existe** (whatsapp_inbox#29): no había command detrás, y un permiso que no
gatea nada contesta «sí» a una auditoría que debería decir que no.

## Qué expone hoy

| Tipo | Nombre | Permiso |
| ---- | ------ | ------- |
| query | `conversations.list` / `.get` · `messages.list` | `view_conversation` |
| query | `requests.list` / `.get` | `view_request` |
| query | `templates.list` · `settings.get` | `manage_settings` (solo admin) |
| command | `requests.approve` / `.reject` / `.fulfill` (WASM) | `change_request` |
| command | `requests.delete` (rechaza si ya está `fulfilled`) | `delete_request` |
| command | `conversations.assign` · `templates.create/update/delete` · `settings.upsert` | `manage_settings` |
| command | `messages.ingest` · `requests.ingest` (WASM) | `manage_connections` |
| emite | `message.received`, `request.created/approved/rejected/fulfilled/deleted`, `conversation.assigned`, `template.*`, `settings.updated` | — |
| escucha | `hub.whatsapp.message_received` (core) · `appointments.booking_request.fulfilled` / `.failed` | — |

Navegación: `erp-whatsapp-inbox-inbox`, `-requests`, `-templates`.

## Layout

```text
module.json                   # manifest (contrato técnico)
migrations/                   # esquema §2.5 + contador atómico de reference_number (ADR-0008)
queries/*.sql                 # lecturas declarativas (:hub_id inyectado)
commands/*.sql                # escrituras declarativas (las `_` son intenciones del WASM)
schemas/*.json                # JSON Schemas de input (draft 2020-12)
handler/                      # WASM Tier 2 parcial → dist/handler.wasm
ui/                           # Web Components (Lit/Ionic/OutfitKit)
docs/                         # documentación de usuario + corpus del asistente
```

## Estado y trabajo abierto

**Ya no está congelado** (pm#112, ADR-0283): es el caso estrella del kernel de automatización.

El «bloqueo» del dispatch cross-módulo de `fulfill_request` **no es un pendiente**: está prohibido a
propósito y la prohibición se reforzó (hub#659, ADR-0283 §7). Reaccionar ejecutando el command de
otro módulo es territorio de un **flujo con grant explícito** —auditable y revocable—, no de un
handler. Ver la tabla de decisiones al principio de [`WASM-TODO.md`](WASM-TODO.md), donde tres piezas
de esa lista quedaron descartadas por la misma razón.

Abierto: pantalla de ajustes del canal (whatsapp_inbox#6) y el emit condicional del runtime
([hub#1076](https://github.com/ERPlora/hub/issues/1076)).

Doc de arquitectura: `architecture/_frozen/modules/whatsapp_inbox.md` (pendiente de mover).

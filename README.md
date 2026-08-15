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
> - **No se puede ENVIAR un mensaje**: existe el permiso `send_message` y **no existe el command**.
> - **Nada trae los mensajes**: no hay webhook ni allowlist de red a Meta declarada en el manifest.
> - **Las auto-respuestas se configuran y no se envían.** Las plantillas guardan su estado en Meta y
>   **nadie lo sincroniza**.

<!-- -->

> **Module id:** `whatsapp_inbox`. **Depende de:** `customers` (referencia blanda, por queries
> públicas, sin FK). Módulo híbrido: SQL + handler WASM **parcial**
> (`fulfill_request`, `parse_inbound_message`).
> ❄️ **Congelado**: su doc de arquitectura vive en `architecture/_frozen/modules/whatsapp_inbox.md`.

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

⚠️ `send_message` lo tienen los tres roles y **no da acceso a nada** (no hay command detrás).

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
| escucha | — (bloque declarado y **vacío**) | — |

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

Módulo **congelado**. El bloqueo de fondo es una decisión del **modelo de comandos del runtime**
(whatsapp_inbox#3): mientras `validate_operation` rechace operaciones hacia commands de otros
módulos, `fulfill_request` no puede cumplir su función. El `reference_number` sí quedó resuelto
**module-side** (ADR-0008, whatsapp_inbox#5).

Doc de arquitectura: `architecture/_frozen/modules/whatsapp_inbox.md`.

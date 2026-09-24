# El e2e del caso estrella — cómo se corre, y qué prueba de verdad

`whatsapp_appointment_e2e.rs` recorre la cadena entera contra el **runtime real** del hub, con los
**módulos publicados** (no fixtures) y **Postgres real**:

```text
evento core hub.whatsapp.message_received  →  el listener de ESTE módulo  →  conversación + mensaje
                                           →  el trigger del flujo        →  _flow_runs
                                           →  el step notify              →  «te confirmo en cuanto abramos»
                                           →  el step ai                  →  se le pasa al server
```

Vive aquí y no en `hub/crates/runtime/tests/` porque lo que prueba es **producto**: el listener de
este manifest y la plantilla de `flows/`. Necesita un checkout del hub para correr, así que se copia
allí (es un fichero, sin dependencias del repo del hub más allá del propio crate).

## Cómo

```bash
HUB=/ruta/al/checkout/de/hub          # una rama que lleve hub#821 (step `notify`)
MODS=/ruta/a/modules-workspace/modules

docker run -d --name erplora-e2e-pg -e POSTGRES_PASSWORD=test -p 5435:5432 pgvector/pgvector:pg18-trixie
cp tests/e2e/whatsapp_appointment_e2e.rs "$HUB/crates/runtime/tests/"

cd "$HUB" && DATABASE_URL="postgres://postgres:test@localhost:5435/hub_test" \
  ERPLORA_MODULES_DIR="$MODS" \
  cargo test -p erplora-runtime --test whatsapp_appointment_e2e
```

### `known_customer_link_e2e.rs` (whatsapp_inbox#149)

La conversación aprende de quién es **sin ninguna automatización**: evento core → `_ingest_inbound_message`
→ `whatsapp_inbox.message.received` → `_link_known_customer` (handler WASM con `customers.list`
pre-cargada por `reads`) → `_link_known_customer_write`. Instala solo `customers` y este módulo, así
que el directorio de módulos necesita esos dos:

```bash
cp tests/e2e/known_customer_link_e2e.rs "$HUB/crates/runtime/tests/"
cd "$HUB" && DATABASE_URL=… ERPLORA_MODULES_DIR="$MODS" \
  cargo test -p erplora-runtime --test known_customer_link_e2e
```

Control negativo medido: contra `whatsapp_inbox@main` sin el listener caen 2 de los 3 (el hilo
queda con `customer_id` `Null`); el tercero —un número que nadie tiene en ficha— sigue verde, como
debe.

## Qué NO prueba, y por qué no puede

- **El mensaje de WhatsApp real.** El evento se inserta como lo inserta `inbound_poll.rs`
  (`_event_outbox.id = "wa-<wa_message_id>"`), que es donde acaba un mensaje de Meta. Lo de antes
  —webhook de Meta → SaaS → poller— es hub#664/saas#1353 y ya está mergeado; aquí empieza el tramo
  que este PR toca.
- **Los turnos de IA.** Un step `ai` es un `PendingIo::Ai` que despacha `crates/server` por el proxy
  del SaaS con el token de máquina del hub: no hay modelo al final de un test de runtime, **por
  diseño** (ARQUITECTURA.md §9.3, el hub nunca habla con un LLM). Lo que sí queda fijado es que el
  run **llega** a ese step y lo entrega.
- **El envío real por Meta.** El step `notify` **encola** (`flow.reminder.due`); quien habla con la
  red es el relay del outbox por el proxy del SaaS. El test comprueba la fila encolada, su
  destinatario y el `resolved_via` que nombra el grant.

## El control negativo (esto es lo que hace que el verde signifique algo)

Con el `module.json` **sin** `events.listen` —es decir, el estado en el que estaba este módulo— tres
de los cuatro tests caen, y caen por el motivo del issue:

```text
the_core_event_lands_in_the_inbox_…      left: 0  right: 1   («one contact, one thread»)
the_customer_who_writes_at_3am_…         el step notify no encuentra a nadie a quien escribir
with_the_ai_steps_…                      el run termina en `failed`, no en `done`
```

El que sigue verde es el de la plantilla, y también es correcto: un documento de flujo válido lo es
tenga o no tenga el módulo su listener. Sin el listener el flujo se guarda, se arma… y a las 3 de la
mañana no contesta nadie.

### `her_typed_choice_finds_the_list_she_was_offered` (whatsapp_inbox#76)

Dentro de `whatsapp_appointment_e2e.rs`. Hace de modelo (`complete_flow_io`) y recorre tres
mensajes: le ofrece dos huecos → la conversación los recuerda; contesta «el 2» → el run nuevo los
encuentra en `recall_offer` ANTES del paso `ai`; reserva (`slots: []`) → la oferta se vacía y un «el
2» posterior no encuentra nada. Usa solo el trigger del mensaje escrito (hub#2061). Necesita en
`$MODS` `customers`, `taxes`, `services`, `staff`, `schedules`, `appointments` y este módulo, a su
`origin/main` (con checkouts viejos `appointments` no instala).

### `their_typed_choice_finds_the_table_times_they_were_offered` (whatsapp_inbox#174)

La misma cadena de tres mensajes con la receta de **reservas de mesa**: se le ofrecen dos horas →
la conversación las recuerda; contesta «la 2» → `recall_offer` las encuentra ANTES de `book_table`;
reserva → la oferta se vacía. También con solo el trigger escrito (hub#2061). Necesita en `$MODS`
`customers`, `tables`, `reservations` y este módulo.

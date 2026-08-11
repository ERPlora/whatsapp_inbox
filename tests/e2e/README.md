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

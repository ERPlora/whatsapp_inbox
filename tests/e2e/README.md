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

### `recipe_update_e2e.rs` (whatsapp_inbox#241)

Lo que la pantalla de WhatsApp da por hecho al pintar «Hay una versión mejorada» y su «Actualizar»:
activar la receta VIEJA (sintetizada desde la que se publica, sin la disculpa de silencio de #239) →
actualizar el módulo → el hub la marca `outdated` sin tocarla → `restore_flow_template` (la puerta de
`restoreTemplate`, la misma que «restaurar» de la galería) trae la receta nueva, mismo flujo, encendida
o pausada como estaba. El último test es el daño de la issue: antes de actualizar, un asistente mudo
le manda a la clienta un WhatsApp vacío; después, la disculpa. Instala `customers`, `taxes`,
`services`, `staff`, `schedules`, `appointments` y este módulo; se corre en el hub del suelo
(`git worktree add hub-rv-N v1.1.30`):

```bash
cp tests/e2e/recipe_update_e2e.rs "$HUB/crates/runtime/tests/"
cd "$HUB" && DATABASE_URL=… ERPLORA_MODULES_DIR="$MODS" \
  cargo test -p erplora-runtime --test recipe_update_e2e
```

Control positivo medido: con la receta «vieja» igual a la nueva caen los 4.

### `needs_attention_e2e.rs` (whatsapp_inbox#238)

La clienta a la que la automatización no pudo contestar queda marcada «necesita atención» hasta que
alguien del negocio le contesta: escribe → el asistente de la agenda **falla** (o contesta **nada**)
→ la receta publicada le pide perdón y llama a `whatsapp_inbox.conversations.needs_attention` con
`input.from` (sus grants lo permiten) → la lista de la bandeja, en su orden por defecto, la sirve
**la primera** con `needs_attention_at`; un segundo fallo no mueve la fecha; el **eco** de lo que el
dueño contesta desde el móvil (`direction: outbound`, `source: live`) quita la marca. Mismos módulos
en `$MODS` que `recipe_update_e2e.rs`, y en el hub del suelo (`v1.1.30`):

```bash
cp tests/e2e/needs_attention_e2e.rs "$HUB/crates/runtime/tests/"
cd "$HUB" && DATABASE_URL=… ERPLORA_MODULES_DIR="$MODS" \
  cargo test -p erplora-runtime --test needs_attention_e2e
```

Control negativo medido: con `whatsapp_inbox` en `origin/main` sin la marca caen los 3. El
aislamiento entre hubs lo prueba `tests/needs_attention.pg.test.py` (dos hubs en la misma BD).

### `customer_erasure_e2e.rs` (whatsapp_inbox#262)

Borrar los datos de una clienta (RGPD art. 17) borra también sus conversaciones de WhatsApp:
`customers.anonymize` → `customer.anonymized` → `_on_customer_anonymized` deja sus hilos y mensajes
sin ningún dato personal y fuera de la bandeja, sin tocar los de otra clienta; si vuelve a escribir,
abre un hilo nuevo sin vincular; un «Eliminar» simple de la ficha (`customers.delete`) **no** borra
nada. Solo instala `customers` y este módulo, como `known_customer_link_e2e.rs`:

```bash
cp tests/e2e/customer_erasure_e2e.rs "$HUB/crates/runtime/tests/"
cd "$HUB" && DATABASE_URL=… ERPLORA_MODULES_DIR="$MODS" \
  cargo test -p erplora-runtime --test customer_erasure_e2e
```

Control positivo medido: con el oyente desenchufado del manifest caen 2 de 3 (el tercero, el borrado
simple, pasa igual por diseño). El aislamiento entre hubs, la idempotencia y cada columna los prueba
`tests/customer_erasure.pg.test.py` (dos hubs en la misma BD, 20 mutantes ejecutados).

**Desde whatsapp_inbox#264 necesita un hub con hub#2461** (`origin/develop` desde el 04/10; el primer
release que lo lleve, no `v1.1.30`): el borrado vacía también lo que guardó la antigua bandeja de
«Solicitudes» en su tabla apartada `_deprecated_whatsapp_inbox_request`, y un hub sin hub#2461 rechaza
instalar el módulo (`… is outside the module's own prefix`). El test siembra una solicitud en crudo
colgada del hilo de cada clienta y exige que la de Ana se vacíe y la de Eva no. Controles medidos el
04/10: con el módulo de `origin/main` (sin el paso) cae `erasing_a_customer_…` («`600111222` is still
stored»); con el hub en `88c8ea8f^` (sin hub#2461) caen los 3 al instalar.

### `number_erasure_e2e.rs` (whatsapp_inbox#263)

El botón «Borrar datos de este número» para quien no tiene ficha: escribe alguien sin ficha → hilo
sin vincular → un admin llama a `whatsapp_inbox.conversations.erase` con el id del hilo → ese hilo y
sus mensajes quedan sin ningún dato personal y fuera de la bandeja, sin tocar el hilo de otra
persona. Además fija las puertas que solo el runtime aplica: un empleado recibe `permission_denied`,
un id vacío `invalid_payload` (antes de ejecutar SQL) y un hilo que no existe
`whatsapp_inbox.conversation_not_found`, nunca un `200 ok`; y si vuelve a escribir, abre un hilo
nuevo por la ingesta real. Solo instala `customers` y este módulo:

```bash
cp tests/e2e/number_erasure_e2e.rs "$HUB/crates/runtime/tests/"
cd "$HUB" && DATABASE_URL=… ERPLORA_MODULES_DIR="$MODS" \
  cargo test -p erplora-runtime --test number_erasure_e2e
```

Controles positivos medidos: sin el `minLength` del schema cae el de las puertas; con la sentencia de
los mensajes sin efecto (`WHERE 1 = 0`) cae el del borrado. Desde whatsapp_inbox#264 también vacía las
solicitudes de la antigua bandeja colgadas de ese hilo, así que pide el mismo hub con hub#2461; con el
módulo de `origin/main` cae `an_admin_erases_…` («`600333444` is still stored»). El aislamiento entre hubs, la
idempotencia y cada columna los prueba `tests/number_erasure.pg.test.py` (dos hubs en la misma BD,
23 mutantes ejecutados), que además compara el SET con el del borrado desde la ficha.

### `confirmation_exact_number_e2e.rs` (whatsapp_inbox#279)

El «¡Confirmada!» de la receta acompañante sale solo a la conversación del número **exacto** de la
cita, o a nadie: `appointments.appointments.confirm` → `appointments.appointment.confirmed` → la
receta publicada `appointment-confirmed-to-whatsapp` con sus grants → `conversations.by_phone` →
`flow.reminder.due` encolado para ese número, o el run para en el paso que dice por qué
(`has_a_phone`, `phone_is_international`, `has_a_thread`). Instala `customers`, `taxes`,
`services`, `staff`, `schedules`, `appointments` y este módulo, a su `origin/main`; corre en
`origin/develop` del hub:

```bash
cp tests/e2e/confirmation_exact_number_e2e.rs "$HUB/crates/runtime/tests/"
cd "$HUB" && DATABASE_URL=… ERPLORA_MODULES_DIR="$MODS" \
  cargo test -p erplora-runtime --test confirmation_exact_number_e2e
```

Control negativo medido: con la receta de `origin/main` (la que buscaba con `conversations.list`,
filtro «contiene») caen 2 de 5: `600111` encola «¡Confirmada!…» para `+34600111222`, la
conversación de otra persona, y `600 111 222` no para en su propio paso. Mutantes de receta
ejecutados: quitar `phone_is_international`, quitar `has_a_thread`, unir las dos banderas en un
paso, invertir su orden y volver a `conversations.list` como destinatario: cae al menos un test con
cada uno. El aislamiento entre hubs y cada defensa de la consulta los prueba
`tests/thread_by_exact_number.pg.test.py` (dos hubs en la misma BD).

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

### `when_her_card_cannot_be_created_she_is_still_answered` (whatsapp_inbox#83)

Una clienta nueva escribe y `know_the_customer` no consigue crearle la ficha (`customers.create`
rechazado). Con `policy: "auto"` ese rechazo vuelve al turno del modelo como resultado de la
herramienta, así que el paso acaba `done` y SIN ficha detrás. El test hace de modelo y comprueba que
el run sigue igualmente hasta el paso que le escribe: `resolve_customer` le dice al paso de reserva
`count: 0`, el enlace sin id no para el run, y lo que redacta `book_appointment` se encola para
ELLA. Control negativo, ejecutado: quitar el `on_error: "continue"` de `remember_the_customer` → el
run acaba `failed`; meter un `condition` «tiene ficha» antes de reservar → el run acaba sin llegar al
paso que le escribe. Los dos caen. Mismos módulos en `$MODS` que el de #76.

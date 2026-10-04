# WORKFLOW — Bandeja de WhatsApp · Respuestas automáticas

Prefijo: WHATSAPP_INBOX

## Flujos

### WHATSAPP_INBOX-F14 Activar «Reservar citas»
Estado: parcial — la pantalla deja encender también «Reservar mesa» y no avisa: con las dos encendidas cada mensaje arranca las dos recetas y el cliente puede acabar con dos reservas, o con una cita y una mesa
Vertical: peluqueria
Actor: administrador
Pantalla: Ajustes
Pasos:
1. En **Ajustes → ¿Para qué lo usas?**, la tarjeta **Reservar citas** explica qué hace.
2. Pulsar **Activar**: aparece la frase «WhatsApp contestará solo: lee tu agenda, ofrece los huecos libres, reserva, mueve o anula la cita de la clienta que escribe…» con **Activar** y **Ahora no**.
3. Pulsar **Activar**: la tarjeta pasa a «Activo» con **Desactivar** y dice «Listo. Escríbete desde otro móvil: “quiero cita mañana”.».
4. Aparece el interruptor de confirmación (F16).
Entra: lo que el hub dice que hay construido; que Citas, Clientes, Servicios y Personal estén instalados y al día.
Sale: la receta «WhatsApp → cita reservada» y su acompañante «Cita confirmada → WhatsApp» quedan creadas, encendidas y con exactamente los permisos que declaran.
Si falla: la tarjeta dice el motivo y deshace lo que llegó a encender; sin permiso, «Solo un dueño o un administrador puede activarlo.». Si el hub no ofrece la receta: con Citas instalada y otra aplicación que la receta pide ausente, en pausa o vieja (o Citas vieja), la tarjeta se sustituye por «“Reservar citas” necesita la aplicación …» con **Ver aplicaciones**; sin Citas ni Reservas activas, «Instala Citas o Reservas para que WhatsApp reserve solo»; si están pero el hub no ofrece ninguna receta y no dice por qué, «Actualiza Citas o Reservas para que WhatsApp reserve solo»; y con Citas ausente o en pausa pero Reservas activa, la tarjeta de citas no aparece, sin aviso.
Implicados: APPOINTMENTS-F06, APPOINTMENTS-F18, REC_WA_CITA-F01
Pendiente de enlazar: flows — encender una receta de fábrica de un módulo con sus permisos
QA: W-01 (discrepa)

### WHATSAPP_INBOX-F15 Activar «Reservar mesa»
Estado: parcial — la pantalla deja encender también «Reservar citas» y no avisa: con las dos encendidas cada mensaje arranca las dos recetas y el cliente puede acabar con dos reservas, o con una cita y una mesa
Vertical: restaurante
Actor: administrador
Pantalla: Ajustes
Pasos:
1. En **Ajustes → ¿Para qué lo usas?**, la tarjeta **Reservar mesa** explica qué hace.
2. Pulsar **Activar**: aparece «WhatsApp contestará solo: mira las mesas libres, reserva la mesa de quien escribe y le contesta. ¿Lo activas?» con **Activar** y **Ahora no**.
3. Pulsar **Activar**: la tarjeta pasa a «Activo» con **Desactivar** y dice «Listo. Escríbete desde otro móvil: “quiero mesa para dos mañana”.».
4. Aparece el interruptor de confirmación (F16).
Entra: lo que el hub dice que hay construido; que Reservas y Clientes estén instalados y al día.
Sale: la receta «WhatsApp → mesa reservada» creada, encendida y con exactamente sus permisos. No lleva acompañante.
Si falla: igual que F14, nombrando Reservas o Clientes.
Implicados: RESERVATIONS-F17, REC_WA_MESA-F01
Pendiente de enlazar: flows — encender una receta de fábrica de un módulo con sus permisos
QA: WR-01

### WHATSAPP_INBOX-F16 Decidir si las reservas por WhatsApp se confirman solas
Estado: hecho
Vertical: comun
Actor: administrador
Pantalla: Ajustes
Pasos:
1. Con la tarjeta en «Activo», elegir en su interruptor **Las citas se confirman solas** (o **Las reservas se confirman solas**) o **Las reviso yo antes**.
2. Con «Las reviso yo antes» aparece dónde esperan: «Cada cita nueva te espera en la Agenda con “Confirmar”…» o «Cada reserva nueva te espera en Reservas con “Confirmar”…».
3. El cambio se guarda al momento en Citas o en Reservas, no en este módulo.
4. El mismo interruptor no abarca lo mismo en los dos negocios: en Citas solo decide las citas que reserva la propia clienta (las del mostrador nacen siempre Pendiente); en Reservas decide **toda** reserva nueva, también la que se toma a mano y la que sale de la lista de espera.
Entra: la política actual del módulo que lleva la agenda. Sin ajuste guardado, Citas confirma sola y Reservas revisa (son opuestos a propósito).
Sale: la política cambiada en Citas (peluquería) o en Reservas (restaurante); la receta la lee antes de cada reserva y elige la frase que manda. En la peluquería, con «Las citas se confirman solas», la cita nace confirmada y eso dispara también el aviso de F23.
Si falla: «No se pudo guardar cómo se confirman las citas/reservas. Inténtalo otra vez.».
Implicados: APPOINTMENTS-F18, APPOINTMENTS-F19, RESERVATIONS-F04, REC_WA_CITA-F06, REC_WA_MESA-F06
QA: W-03, WR-02

### WHATSAPP_INBOX-F17 Desactivar una respuesta automática
Estado: hecho
Vertical: comun
Actor: administrador
Pantalla: Ajustes
Pasos:
1. En la tarjeta «Activo», pulsar **Desactivar**.
2. La tarjeta pasa a «Desactivada» con **Activar**; WhatsApp deja de contestar solo.
Entra: la tarjeta elegida.
Sale: se apagan primero los acompañantes y la receta de la tarjeta la última, para que nunca quede una respuesta encendida detrás de una tarjeta apagada.
Si falla: la tarjeta dice el motivo y se repinta con lo que de verdad sigue encendido.
Implicados: REC_WA_CITA-F01, REC_WA_MESA-F01
Pendiente de enlazar: flows — apagar una receta de fábrica de un módulo
QA: ninguno

### WHATSAPP_INBOX-F18 Actualizar una respuesta automática a su versión mejorada
Estado: hecho
Vertical: comun
Actor: administrador
Pantalla: Ajustes
Pasos:
1. Si el módulo trae una receta mejor que la que se encendió, la tarjeta dice «Hay una versión mejorada de esta respuesta automática.» con **Actualizar**.
2. Pulsar **Actualizar**: aparece que la nueva sustituye a la actual, también los cambios hechos a mano, y que seguirá encendida o apagada como esté.
3. Confirmar con **Actualizar**: «Hecho: esta respuesta automática ya funciona con la última versión.».
Entra: qué recetas de la tarjeta marca el hub como desfasadas.
Sale: solo esas recetas sustituidas, conservando su encendido e historial.
Si falla: «Esta respuesta automática ya no existe aquí…» (volver a activarla) o «No se pudo actualizar…»; el aviso sigue solo para lo que no se actualizó.
Implicados: REC_WA_CITA-F01, REC_WA_MESA-F01
Pendiente de enlazar: flows — restaurar la versión de fábrica de una receta
QA: ninguno

### WHATSAPP_INBOX-F19 Elegir el hueco escribiendo en vez de tocando
Estado: hecho
Vertical: comun
Actor: cliente
Pantalla: WhatsApp: chat del cliente
Pasos:
1. La respuesta automática le ofrece una lista de horas (botón **Ver huecos** en la cita; horas en la mesa).
2. Ella puede tocar una opción, o escribir `el 2`, `la segunda` o `12:30`.
3. Si lo escrito señala una sola opción ofrecida en las últimas 24 h, se comprueba que sigue libre y se reserva como si la hubiera tocado; si no está claro, vuelve a ofrecer.
Entra: la última lista ofrecida a ese número (solo 24 h).
Sale: la reserva (F21 o F24); la lista se vacía en cuanto reserva, anula o mueve.
Si falla: si guardar la lista falla, ella recibe su respuesta igual y la próxima vez se le vuelve a ofrecer.
Implicados: APPOINTMENTS-F02, RESERVATIONS-F05, REC_WA_CITA-F05, REC_WA_MESA-F05
QA: W-02

### WHATSAPP_INBOX-F20 Cuando el asistente no puede contestar
Estado: hecho
Vertical: comun
Actor: sistema
Pantalla: WhatsApp: chat del cliente
Pasos:
1. Si el asistente falla o no dice nada, el cliente recibe un texto fijo de la receta: en la cita «Perdona, ahora mismo no puedo mirar la agenda. Alguien del equipo te contestará por aquí en cuanto pueda.»; en la mesa, igual con «las reservas».
2. Su conversación queda marcada «Necesita atención» y aparece en la campana (F09).
3. Nada más se le manda en ese turno.
4. La marca **solo** se pone en ese caso. Cuando es el propio asistente quien contesta que alguien del negocio le responderá (la pregunta no es de reservar, el número no identifica a una sola ficha, o en la mesa pide cambiar o anular, F25), la conversación **no** se marca ni sube a la campana, en los dos negocios.
Entra: el resultado del paso del asistente.
Sale: una disculpa y la marca de atención.
Si falla: si la marca no se puede poner, la disculpa sale igual y el mensaje sigue sin leer en la bandeja.
Implicados: REC_WA_CITA-F09, REC_WA_MESA-F09
Pendiente de enlazar: flows — continuar tras un paso fallido y condiciones de paso
QA: ninguno

### WHATSAPP_INBOX-F21 La clienta pide cita por WhatsApp
Estado: hecho
Vertical: peluqueria
Actor: cliente
Pantalla: WhatsApp: chat del cliente
Pasos:
1. La clienta escribe, por ejemplo, `¿Tenéis hueco mañana por la tarde para un corte?`.
2. Recibe al momento el acuse fijo de la receta «¡Gracias por escribirnos! Miro la agenda y te contesto ahora mismo.».
3. Si no tiene ficha, se le crea una con origen WhatsApp.
4. Si su mensaje fija servicio, día y hora y está libre, se reserva con la profesional que trabaja a esa hora; si no, recibe los huecos libres de verdad para tocar o escribir (F19). La receta le ordena al asistente no elegir nunca la hora; lo vigila la batería de recetas sobre el texto del guion, no el código que reserva.
5. Recibe una respuesta que redacta el asistente: que la cita está reservada (día, hora y profesional) si el salón confirma solo, o que se la ha apuntado y el salón se la confirma, según F16. La cita está en la Agenda.
Entra: el mensaje escrito o la opción tocada (no el historial, ni las respuestas del dueño, ni fotos sin texto).
Sale: ficha nueva si hacía falta (Clientes), conversación unida a la ficha, cita aceptada o pendiente (Citas), respuesta por WhatsApp.
Si falla: F20; sin hueco, le dice el porqué y ofrece otros.
Implicados: APPOINTMENTS-F02, APPOINTMENTS-F18, CUSTOMERS-F10, CUSTOMERS-F12, CUSTOMERS-F26, STAFF-F09, REC_WA_CITA-F03, REC_WA_CITA-F04, REC_WA_CITA-F05, REC_WA_CITA-F07
Pendiente de enlazar: services — leer servicios y su duración
QA: W-02, W-06, W-07, L-12

### WHATSAPP_INBOX-F22 La clienta anula o mueve su cita por WhatsApp
Estado: hecho
Vertical: peluqueria
Actor: cliente
Pantalla: WhatsApp: chat del cliente
Pasos:
1. La clienta escribe `no puedo ir` o `¿me la cambias al jueves?`.
2. Se busca su cita por su número; con dos próximas, pregunta cuál.
3. Anular: se anula con las reglas del salón (si se permite y con qué antelación); fuera de plazo se le dice y la cita sigue.
4. Mover: se ofrecen huecos y se mueve la misma cita, conservando profesional y servicio.
5. Recibe la respuesta con lo que ha pasado.
Entra: el mensaje y las citas de esa clienta.
Sale: cita anulada o movida en Citas; nunca la de otra persona.
Si falla: F20; si Citas lo rechaza, se le explica.
Implicados: APPOINTMENTS-F02, APPOINTMENTS-F06, REC_WA_CITA-F08
QA: W-04 (discrepa)

### WHATSAPP_INBOX-F23 La clienta recibe el aviso cuando el salón confirma
Estado: parcial — el aviso es texto libre: si han pasado más de 24 h desde el último mensaje de la clienta, Meta lo rechaza y no hay plantilla de respaldo; con «Las citas se confirman solas» la clienta recibe dos mensajes (la respuesta de la reserva y el aviso de confirmada), sin orden garantizado; y la conversación se busca con el teléfono de la cita como texto contenido en el de la conversación, así que un teléfono con espacios o guiones no la encuentra (no se avisa) y uno incompleto puede dar con la de otra persona
Vertical: peluqueria
Actor: responsable, cliente
Pantalla: WhatsApp: chat del cliente
Pasos:
1. Con «Las reviso yo antes», la encargada pulsa **Confirmar** en la Agenda.
2. Si la clienta tiene conversación de WhatsApp con el negocio, recibe el texto fijo de la receta «¡Confirmada! Te esperamos el {día} a las {hora} para tu {servicio} con {profesional}.», con el día y la hora ya escritos en el idioma y la zona del negocio.
3. La conversación se busca con el teléfono guardado en la cita, como texto contenido en el de la conversación: si en la cita está con espacios o guiones no se encuentra, y si está incompleto puede encontrar la de otra persona. Si no tiene teléfono o no hay conversación, no se manda nada y el motivo queda en el historial de la automatización.
4. El aviso sale con **cualquier** confirmación de una cita cuyo teléfono tenga conversación: también la de una cita del mostrador, y también la de una cita que nace ya confirmada porque «Las citas se confirman solas» está encendido (F16); en ese caso la clienta recibe los dos mensajes, la respuesta de F21 y este aviso, en cualquier orden (salen de dos automatizaciones distintas).
Entra: la cita confirmada (Citas) y la conversación de su teléfono.
Sale: un WhatsApp a la clienta.
Si falla: el motivo queda en el historial de la automatización; nada se ve en la Agenda.
Implicados: APPOINTMENTS-F03, APPOINTMENTS-F18, CUSTOMERS-F11, REC_WA_CITA-F07
QA: W-03, BD-07, WA-04

### WHATSAPP_INBOX-F24 El cliente pide mesa por WhatsApp
Estado: hecho
Vertical: restaurante
Actor: cliente
Pantalla: WhatsApp: chat del cliente
Pasos:
1. El cliente escribe, por ejemplo, `Mesa para 4 el sábado a las 21`.
2. Recibe al momento el acuse fijo de la receta «¡Gracias por escribirnos! Miro el libro de reservas y te contesto ahora mismo.».
3. Se mira si ese día cierra, los turnos y las plazas libres; la receta le ordena al asistente que la hora y cuántos sois los diga el cliente (lo vigila la batería sobre el guion).
4. Si hay sitio, se reserva; si no, se le ofrecen horas para tocar o escribir (F19), o se le apunta en la lista de espera.
5. Recibe una respuesta que redacta el asistente: que la mesa está reservada, o que se la ha apuntado y el restaurante se la confirma, según F16.
Entra: el mensaje escrito o la opción tocada; su ficha si ya existe (no se crea).
Sale: reserva aceptada o pendiente, o entrada en la lista de espera (Reservas), con su teléfono y el nombre que dé en el mensaje (si no da ninguno, su teléfono hace de nombre; aunque tenga ficha, el nombre no se toma de ella, solo queda ligada); respuesta por WhatsApp.
Si falla: F20; sin plazas o con demasiados comensales, se le explica.
Implicados: CUSTOMERS-F10, RESERVATIONS-F01, RESERVATIONS-F02, RESERVATIONS-F05, RESERVATIONS-F14, RESERVATIONS-F17, REC_WA_MESA-F03, REC_WA_MESA-F04, REC_WA_MESA-F05, REC_WA_MESA-F07
QA: WR-02, WR-03, WR-04

### WHATSAPP_INBOX-F25 El cliente anula o cambia su mesa por WhatsApp
Estado: no hecho — Reservas ya acepta cambiar o anular desde el canal del cliente comprobando que la reserva es suya (reservations#50), pero la receta de mesa no lo usa: hoy se le contesta que alguien del restaurante se ocupa y la conversación no se marca «Necesita atención», así que nadie recibe aviso en la campana
Vertical: restaurante
Actor: cliente
Pantalla: WhatsApp: chat del cliente
Pasos:
1. El cliente escribe `no podemos ir` o `¿podemos pasarla a las 22?`.
2. Hoy recibe que alguien del restaurante se ocupa; la reserva no se toca y la conversación no sube a la campana (F09): solo lo ve quien abra la bandeja o el móvil.
3. Cuando exista: se busca su reserva por su número, se anula o cambia con las reglas del restaurante y se le contesta.
Entra: el mensaje y las reservas de ese cliente.
Sale: hoy, nada; cuando exista, reserva anulada o cambiada.
Si falla: sin confirmar (no existe todavía).
Implicados: RESERVATIONS-F18, REC_WA_MESA-F08
QA: WR-03

### WHATSAPP_INBOX-F26 El cliente recibe el aviso cuando el restaurante confirma
Estado: no hecho — no hay receta acompañante para Reservas; un cliente al que se le dijo que se la confirmarían no recibe nada al confirmarla
Vertical: restaurante
Actor: responsable, cliente
Pantalla: WhatsApp: chat del cliente
Pasos:
1. Con «Las reviso yo antes», el encargado confirma la reserva en Reservas.
2. Hoy el cliente no recibe nada; cuando exista, recibe la confirmación con día, hora y comensales.
Entra: la reserva confirmada (Reservas).
Sale: hoy, nada.
Si falla: sin confirmar (no existe todavía).
Implicados: RESERVATIONS-F07, RESERVATIONS-F19, REC_WA_MESA-F07
QA: ninguno

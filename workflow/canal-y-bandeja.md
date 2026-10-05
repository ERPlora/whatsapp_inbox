# WORKFLOW — Bandeja de WhatsApp · Canal y bandeja

Prefijo: WHATSAPP_INBOX

## Flujos

### WHATSAPP_INBOX-F01 Conectar el número de WhatsApp del negocio
Estado: parcial — hoy Meta solo deja conectar números del portfolio de ERPlora (verificación del negocio y revisión de la app pendientes, pm#277)
Vertical: comun
Actor: administrador
Pantalla: Ajustes
Pasos:
1. Abrir **Bandeja de WhatsApp → Ajustes**; el bloque **Tu número** dice que no hay número.
2. Pulsar **Conectar WhatsApp**: se abre la ventana de Facebook.
3. Iniciar sesión, elegir conectar la app de WhatsApp Business, escribir el número y escanear el QR con la app del móvil; aceptar compartir el historial.
4. El bloque pasa a «Conectado» con el número y **Desconectar**; la etiqueta «App de WhatsApp Business» no sale, porque la plataforma no dice al hub si el número viene de la app. Se comprueba escribiendo al número desde otro móvil (F03).
Entra: el código que devuelve Meta tras el QR.
Sale: el número queda conectado en la plataforma (el hub solo sabe cuál es); empiezan a llegar los mensajes y el historial de los últimos meses. Por ese número salen también los WhatsApp que manda una automatización del negocio (FLOWS-F15).
Si falla: el bloque dice el motivo («La conexión se canceló…», «No se pudo abrir la ventana de Facebook…», «Solo un dueño o un administrador…») y deja reintentar; si falla la plataforma o Meta (WhatsApp no configurado, Meta no contesta o rechaza, sin cuenta de WhatsApp Business o sin permiso de Facebook), el motivo no llega y sale el genérico «Algo ha fallado al conectar. Inténtalo de nuevo en un minuto.»; un hub viejo ve «Este hub es demasiado antiguo para conectar el número desde aquí…».
Implicados: FLOWS-F15, REC_WA_CITA-F01, REC_WA_MESA-F01
Pendiente de enlazar: hub — bloque «Tu número» del shell (abre la ventana de Meta y pasa el código a la plataforma)
Pendiente de enlazar: saas — pasarela de WhatsApp: canjea el código, guarda el token y suscribe el número
QA: WA-01, WA-07

### WHATSAPP_INBOX-F02 Desconectar o volver a conectar el número
Estado: hecho
Vertical: comun
Actor: administrador
Pantalla: Ajustes
Pasos:
1. En **Tu número**, pulsar **Desconectar** y confirmar «¿Desconectar este número? Los mensajes dejarán de llegar aquí.».
2. Si WhatsApp retiró el permiso, el número aparece con «Hay que reconectar» y la explicación; pulsar **Volver a conectar WhatsApp** y repetir F01.
3. Se comprueba que el bloque vuelve a «Conectado» y que un mensaje nuevo llega.
Entra: el número elegido.
Sale: la plataforma deja de recoger (o vuelve a recoger) los mensajes de ese número. Las conversaciones guardadas no se tocan.
Si falla: el bloque dice el motivo y ofrece **Reintentar**.
Implicados: REC_WA_CITA-F01, REC_WA_MESA-F01
Pendiente de enlazar: hub — bloque «Tu número» del shell (desconectar y reconectar)
Pendiente de enlazar: saas — pasarela de WhatsApp: baja del número y renovación del token
QA: WA-01, WA-09

### WHATSAPP_INBOX-F03 Recibir un mensaje en la bandeja
Estado: parcial — con el cupo del mes agotado las respuestas automáticas corren igual (gastan un turno del asistente y pueden reservar) aunque su respuesta no sale y la bandeja no guarda el mensaje
Vertical: comun
Actor: cliente, sistema
Pantalla: Bandeja de entrada
Pasos:
1. La clienta escribe al número del negocio.
2. En pocos segundos su conversación aparece arriba en **Bandeja de entrada** con **Sin leer** sumado y la hora en **Último mensaje**; si la bandeja está abierta, se refresca sola.
3. Un mensaje que llega dos veces aparece una sola vez. Los mensajes del historial que trae la conexión aparecen con la hora en que se dijeron y no suman en **Sin leer**.
Entra: cada mensaje que el hub recoge de la plataforma (número de la persona, texto, objeto de Meta, si es entrante o la respuesta del dueño, si es en vivo o historial).
Sale: una conversación por número y el mensaje guardado; aviso público de mensaje recibido (`whatsapp_inbox.message.received`) que dispara F04; el aviso del hub con el mismo mensaje es el que arranca las recetas (F21, F24). El aviso público también puede arrancar las automatizaciones que monta el negocio en Automatizaciones (la tarjeta de mensajes sin contestar, FLOWS-F04); Automatizaciones avisa de las que saltan también con los mensajes propios o el historial y las repara (FLOWS-F11).
Si falla: con el cupo del mes agotado el mensaje entrante en vivo no se guarda y nada lo dice en la bandeja (ver F13), pero las respuestas automáticas corren igual: gastan un turno del asistente y pueden reservar; lo que no sale es su respuesta; si el hub está apagado los mensajes esperan en la plataforma.
Implicados: FLOWS-F04, FLOWS-F11, REC_WA_CITA-F02, REC_WA_MESA-F02
Pendiente de enlazar: hub — recogida periódica de mensajes de WhatsApp de la plataforma y su aviso al núcleo
Pendiente de enlazar: saas — pasarela de WhatsApp: recibe de Meta y aparca por hub
QA: WA-02, WA-08

### WHATSAPP_INBOX-F04 Reconocer a la clienta por su número
Estado: hecho
Vertical: comun
Actor: sistema
Pantalla: ninguna
Pasos:
1. Cuando escribe alguien cuyo número está en una ficha de cliente, su conversación queda unida a esa ficha.
2. Cuando se crea o corrige una ficha con el número de alguien que ya había escrito, su conversación se une a ella al guardar.
3. Cada conversación sin ficha se repasa sola **una** vez, en tandas de 200 cada 15 minutos (primero las más antiguas); si en ese repaso no hay ficha, ya no se vuelve a mirar hasta que ella escriba o se guarde su ficha.
4. El número se compara como número: `600 111 222`, `+34 600 111 222` y `0034600111222` son la misma persona en un negocio de España; los mismos dígitos con el prefijo de otro país son otra persona.
Entra: el número de la conversación; las fichas con ese número (Clientes); el país del negocio.
Sale: la conversación sabe de qué ficha es. Solo rellena un vínculo vacío: el que puso una persona o una receta se respeta.
Si falla: si dos fichas tienen el mismo número, o la búsqueda no responde, no se une a nadie y el mensaje sigue guardado.
Implicados: CUSTOMERS-F01, CUSTOMERS-F04, CUSTOMERS-F08, CUSTOMERS-F10, CUSTOMERS-F11, CUSTOMERS-F18, REC_WA_CITA-F03, REC_WA_MESA-F03
QA: ninguno

### WHATSAPP_INBOX-F05 Leer una conversación
Estado: parcial — abrir el hilo no baja «Sin leer» (nada lo baja salvo borrar), y la columna Contacto enseña el teléfono porque el nombre de perfil de WhatsApp no llega
Vertical: comun
Actor: empleado, responsable, administrador
Pantalla: Bandeja de entrada
Pasos:
1. Abrir **Bandeja de WhatsApp → Bandeja de entrada**; buscar por contacto o teléfono o filtrar por columna si hace falta.
2. Pulsar **Abrir** en la fila (o tocar la fila).
3. El hilo aparece encima de la lista, del mensaje más antiguo al más reciente, con la hora de cada uno; un mensaje sin texto ni adjunto (una ubicación, un botón) enseña el tipo que da Meta tal cual, en inglés (`location`, `button`…); y un mensaje del que no se sabe quién lo envió lleva «Mensaje no reconocido».
4. Pulsar **Cerrar** para volver a la lista.
Entra: la conversación y sus mensajes de este negocio.
Sale: nada; solo lee.
Si falla: el motivo que devuelve el hub dentro del panel, o «No se pudo cargar la conversación» si no trae ninguno; la lista sigue disponible.
Implicados: ninguno
QA: WA-10 (discrepa)

### WHATSAPP_INBOX-F06 Ver una foto, una nota de voz o un documento
Estado: hecho
Vertical: comun
Actor: empleado, responsable, administrador
Pantalla: Bandeja de entrada
Pasos:
1. Abrir una conversación (F05): las fotos y stickers aparecen en el hilo con su texto.
2. Tocar una foto para verla en grande; pasar con las flechas y cerrar con **Cerrar**.
3. En una nota de voz o un vídeo, pulsar **Reproducir**; en un documento, **Descargar**. Mientras baja se lee «Cargando el adjunto…».
4. Si el dispositivo no puede reproducirlo (notas de voz en Safari), el botón dice **Descargar** y la burbuja lo explica.
Entra: el adjunto, pedido a la plataforma solo al abrir o al pulsar.
Sale: nada; el archivo solo se guarda mientras el hilo está abierto.
Si falla: «No se ha podido cargar el adjunto.» con **Reintentar**; en un hub sin esa puerta, «Este adjunto aún no se puede ver aquí…».
Implicados: pendiente
Pendiente de enlazar: hub — puerta de adjuntos de WhatsApp
QA: WA-10 (discrepa)

### WHATSAPP_INBOX-F07 Asignar una conversación a alguien del equipo
Estado: parcial — se teclea el identificador del empleado en vez de elegirlo de una lista, y asignar no cambia lo que ve cada persona
Vertical: comun
Actor: administrador
Pantalla: Bandeja de entrada
Pasos:
1. Abrir la conversación (F05).
2. En **Asignada a**, escribir el identificador del empleado (vacío = nadie).
3. Pulsar **Asignar** (o **Desasignar** con el campo vacío).
4. El hilo y la lista se recargan con la asignación.
Entra: la conversación y el empleado.
Sale: la conversación queda asignada; aviso público de conversación asignada (`whatsapp_inbox.conversation.assigned`).
Si falla: «No se pudo asignar la conversación» (o el motivo) bajo el campo; no viaja a otra conversación.
Implicados: ninguno
QA: ninguno

### WHATSAPP_INBOX-F08 Contestar desde la app de WhatsApp Business del móvil
Estado: hecho
Vertical: comun
Actor: administrador
Pantalla: Bandeja de entrada
Pasos:
1. Contestar a la clienta como siempre, desde la app WhatsApp Business del móvil.
2. La respuesta aparece en el hilo de esa clienta en la bandeja del hub, como mensaje del negocio.
3. No suma en **Sin leer**, no gasta cupo, no arranca las respuestas automáticas y quita la marca «Necesita atención» si la tenía.
Entra: el eco de lo que el dueño escribió en el móvil.
Sale: el mensaje en el hilo correcto; la marca de atención quitada.
Si falla: si el hub es antiguo y no distingue el eco, la respuesta podría no aparecer (sin confirmar en hubs actuales).
Implicados: REC_WA_CITA-F09, REC_WA_MESA-F09
Pendiente de enlazar: hub — recogida de los ecos del móvil y del historial
QA: W-05, WA-02

### WHATSAPP_INBOX-F09 Ver quién espera respuesta
Estado: hecho
Vertical: comun
Actor: empleado, responsable, administrador
Pantalla: Hub: Campana de avisos
Pasos:
1. Cuando el asistente de la respuesta automática falla o no dice nada (F20), la campana del hub muestra «Clientes de WhatsApp esperando respuesta» con cuántos, en cualquier pantalla.
2. Tocar la campana abre la **Bandeja de entrada**, con esas conversaciones arriba y la marca «Necesita atención».
3. Al abrir una, el aviso explica que se quita contestando desde el móvil.
4. Contestar desde la app del móvil (F08): la marca y el número de la campana desaparecen.
5. No suben a la campana las conversaciones a las que el propio asistente contestó que alguien del negocio le responderá (otra pregunta, número que no identifica a una sola ficha, cambio o anulación de mesa), ni en la peluquería ni en el restaurante: esas solo se ven abriendo la bandeja.
Entra: las conversaciones marcadas por la receta.
Sale: nada nuevo; la marca solo la quita la respuesta del negocio (ni el siguiente mensaje de la clienta ni el historial).
Si falla: si la campana no se puede leer, el hub no la pinta; la marca sigue en la bandeja.
Implicados: REC_WA_CITA-F09, REC_WA_MESA-F09
Pendiente de enlazar: hub — campana de avisos del shell
QA: ninguno

### WHATSAPP_INBOX-F10 Borrar los datos de un número sin ficha
Estado: parcial — el módulo borra lo suyo, pero el historial interno del hub conserva el texto 90 días (hub#2474) y la plataforma guarda los mensajes no recogidos (saas#1930)
Vertical: comun
Actor: administrador
Pantalla: Bandeja de entrada
Pasos:
1. Abrir la conversación de la persona que pide borrar sus datos (F05).
2. Pulsar **Borrar datos de este número**.
3. Leer «¿Borrar los datos de este número?» con el número y el aviso de que no se puede deshacer; pulsar **Borrar datos** (o **Cancelar**).
4. El hilo se cierra, la lista se recarga sin él y aparece «Se han borrado los datos de este número.».
Entra: la conversación elegida.
Sale: mensajes, nombre, número, huecos ofrecidos y solicitudes antiguas vaciados; conversación cerrada y borrada. Si vuelve a escribir, empieza una conversación nueva.
Si falla: «No se pudieron borrar los datos de este número» (o el motivo) en el panel; el hilo sigue abierto.
Implicados: pendiente
Pendiente de enlazar: hub — borrar del historial interno lo que nombra a la persona
QA: WA-06 (discrepa), L-11

### WHATSAPP_INBOX-F11 Borrar los datos de una clienta desde su ficha
Estado: parcial — mismo resto en el hub que F10 (hub#2467, hub#2477); solo alcanza conversaciones unidas a la ficha
Vertical: comun
Actor: sistema
Pantalla: ninguna
Pasos:
1. En Clientes, el administrador borra los datos de una ficha.
2. Todas las conversaciones unidas a esa ficha quedan vaciadas y cerradas como en F10, sin más pasos.
3. Eliminar una ficha sin borrar sus datos no toca las conversaciones.
Entra: el aviso de ficha anonimizada (Clientes).
Sale: lo mismo que F10, para cada conversación de la ficha.
Si falla: el aviso se reintenta hasta 8 veces (unos 4 minutos) y, si sigue fallando, queda en «Eventos caídos» del hub con los datos dentro hasta que alguien lo reenvía o lo cierra; repetirlo no cambia nada.
Implicados: CUSTOMERS-F16
QA: WA-06 (discrepa), L-11

### WHATSAPP_INBOX-F12 Unir dos fichas de la misma clienta
Estado: hecho
Vertical: comun
Actor: sistema
Pantalla: ninguna
Pasos:
1. En Clientes se unen dos fichas duplicadas.
2. Las conversaciones de la ficha absorbida pasan a la que queda, sin tocar nada más.
Entra: el aviso de fichas unidas (Clientes).
Sale: el vínculo de las conversaciones corregido.
Si falla: el aviso se reintenta hasta 8 veces (unos 4 minutos) y, si sigue fallando, queda en «Eventos caídos» del hub con los datos dentro hasta que alguien lo reenvía o lo cierra; repetirlo no cambia nada.
Implicados: CUSTOMERS-F13
QA: ninguno

### WHATSAPP_INBOX-F13 Ver el consumo del mes y llegar al tope
Estado: parcial — al llegar al tope la pestaña Plan lo dice, pero nada dice que los mensajes entrantes en vivo dejan de guardarse en la bandeja
Vertical: comun
Actor: administrador
Pantalla: Hub: Plan
Pasos:
1. Abrir la pestaña **Plan** del módulo.
2. Ver los mensajes gastados este mes frente al tope del plan; los dos números los pone la plataforma y el hub los copia una vez al día (y al arrancar): el consumo puede ir hasta 24 h por detrás, y justo tras instalar el módulo no hay tope hasta la siguiente vuelta.
3. Al llegar al tope, la pestaña dice «Has consumido todo lo que incluye tu plan este mes.».
4. Al cambiar de mes el gastado vuelve a cero aunque la plataforma aún no haya hablado.
Entra: el tope y el gasto del mes que manda la plataforma.
Sale: nada; no se edita desde el hub.
Si falla: si la pestaña no puede leerlo, dice que no está disponible; al agotar el cupo la plataforma rechaza los envíos: el envío cae al momento a «Eventos caídos» del hub, donde se reenvía a mano, y la bandeja deja de guardar lo que entra. Un freno de tasa de la plataforma se confunde con el cupo agotado y acaba igual.
Implicados: REC_WA_CITA-F02, REC_WA_MESA-F02
Pendiente de enlazar: hub — pestaña Plan del shell
Pendiente de enlazar: saas — cuenta de mensajes facturables y tope del plan
QA: WA-03

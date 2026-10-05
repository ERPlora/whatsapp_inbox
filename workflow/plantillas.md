# WORKFLOW — Bandeja de WhatsApp · Plantillas de Meta

Prefijo: WHATSAPP_INBOX

## Flujos

### WHATSAPP_INBOX-F27 Ver las plantillas y lo que dice Meta de cada una
Estado: hecho
Vertical: comun
Actor: administrador
Pantalla: Plantillas de Meta
Pasos:
1. Abrir **Bandeja de WhatsApp → Ajustes**: en ese momento, aunque no se despliegue nada, las plantillas se ponen al día con Meta una vez (nunca con un temporizador).
2. Desplegar **Plantillas de Meta**: **Estado en Meta** dice «Sin enviar a Meta», «En revisión», «Aprobada», «Rechazada», «Pausada por Meta», «Desactivada por Meta» o «Borrada en WhatsApp Manager».
3. Pulsar **Editar** (o tocar la fila) en una plantilla: el panel enseña su estado, qué hacer («Puedes enviarla cuando quieras…», «Meta la ha rechazado…») y, si la rechazó, «Motivo de Meta: …».
Entra: las plantillas guardadas aquí y lo que Meta dice hoy de cada una (por nombre e idioma).
Sale: el veredicto nuevo guardado en cada plantilla que cambió; una que Meta tuvo y ya no lista queda como «Borrada en WhatsApp Manager» y no se elimina. Automatizaciones lee esta lista para ofrecer las plantillas aprobadas en un paso de mensaje (FLOWS-F15).
Si falla: «No hemos podido comprobar con Meta si hay veredictos nuevos, así que lo que ves es lo último que sabemos…»; la lista sigue visible.
Implicados: FLOWS-F15
Pendiente de enlazar: hub — puerta de plantillas de WhatsApp (listar, registrar, subir muestra)
Pendiente de enlazar: saas — pasarela de WhatsApp: plantillas contra Meta
QA: WA-04

### WHATSAPP_INBOX-F28 Traer las plantillas creadas en WhatsApp Manager
Estado: parcial — no se traen las que llevan carrusel, oferta por tiempo limitado, botón de copiar código o de Flow, cabecera de ubicación o más de una variable en la cabecera
Vertical: comun
Actor: sistema
Pantalla: Plantillas de Meta
Pasos:
1. Al abrir **Ajustes** (no hace falta desplegar Plantillas de Meta), las que el negocio creó en WhatsApp Manager y no están aquí aparecen en la lista con su texto, cabecera, botones, ejemplos y estado.
2. Las que no se pueden traer se nombran en un aviso encima de la tabla («Estas plantillas de WhatsApp Manager todavía no se pueden traer…: nombre (idioma)»).
3. Una plantilla borrada aquí no vuelve a traerse.
Entra: la lista de Meta con el contenido de cada plantilla.
Sale: plantillas nuevas guardadas una sola vez por nombre e idioma; aviso público de plantilla creada.
Si falla: si una no se puede guardar, se nombra en el aviso y se dice el motivo.
Implicados: pendiente
Pendiente de enlazar: saas — pasarela de WhatsApp: plantillas contra Meta
QA: ninguno

### WHATSAPP_INBOX-F29 Crear una plantilla y mandarla a revisión
Estado: parcial — el panel no tiene campo para la cabecera de texto ni para el pie, no crea botones de enlace con variable (whatsapp_inbox#219) ni plantillas de autenticación con su código, y el idioma se escribe a mano
Vertical: comun
Actor: administrador
Pantalla: Plantillas de Meta
Pasos:
1. Pulsar **Añadir** en la barra de la tabla: se abre el panel vacío.
2. Escribir **Nombre** (minúsculas, números y guiones bajos), **Idioma** (por ejemplo `es`) y elegir **Categoría**.
3. Elegir **Cabecera**: Texto, Imagen, Vídeo o Documento (PDF); para un archivo, **Elegir archivo de ejemplo** (JPEG/PNG hasta 5 MB, MP4 hasta 16 MB, PDF hasta 100 MB).
4. Escribir el **Cuerpo**; por cada variable (`{{1}}` o `{{nombre}}`) rellenar su **Ejemplo**.
5. Opcional: **Añadir botón** (hasta 10: respuestas rápidas, hasta 2 enlaces `https://` y 1 llamada con prefijo de país), cada uno con texto de hasta 25 caracteres.
6. Pulsar **Añadir** (desactivado mientras falte el nombre, un ejemplo, el archivo o un dato de un botón). Se guarda aquí y se manda a Meta; el panel se cierra y la plantilla encabeza la lista «En revisión».
Entra: lo que escribe el administrador.
Sale: la plantilla guardada aquí y registrada en Meta con su veredicto; aviso público de plantilla creada.
Si falla: la plantilla queda guardada aquí y el panel sigue abierto, ya como edición, con el motivo encima de **Guardar** (por ejemplo «Meta no ha aceptado el nombre…», «Meta necesita un ejemplo para cada hueco…», «Meta no ha contestado…»); guardarla otra vez no la duplica.
Implicados: pendiente
Pendiente de enlazar: hub — puerta de plantillas de WhatsApp (listar, registrar, subir muestra)
Pendiente de enlazar: saas — pasarela de WhatsApp: plantillas contra Meta
QA: WA-04

### WHATSAPP_INBOX-F30 Editar una plantilla
Estado: parcial — la cabecera de texto, su ejemplo y el pie no se pueden cambiar (viajan intactos); una plantilla con botón de enlace con variable, o con archivo en un hub sin la puerta de muestras, queda en solo lectura
Vertical: comun
Actor: administrador
Pantalla: Plantillas de Meta
Pasos:
1. Pulsar **Editar** en la fila: el panel se abre con sus datos y su veredicto de Meta.
2. Cambiar lo necesario; con cabecera de archivo, volver a elegir el archivo de ejemplo (Meta lo pide en cada guardado).
3. Pulsar **Guardar**: vuelve a revisión de Meta («En revisión») si algo de lo que Meta revisa ha cambiado.
4. En solo lectura el panel explica que se cambia en WhatsApp Manager y no ofrece **Guardar**.
Entra: la plantilla y los cambios.
Sale: la plantilla actualizada aquí y registrada otra vez en Meta; aviso público de plantilla actualizada.
Si falla: como F29; un veredicto de Meta nunca se guarda sobre un texto que se cambió después.
Implicados: pendiente
Pendiente de enlazar: saas — pasarela de WhatsApp: plantillas contra Meta
QA: ninguno

### WHATSAPP_INBOX-F31 Borrar una plantilla
Estado: parcial — borrar aquí no la borra en Meta (el hub ya tiene la puerta para hacerlo y el módulo no la usa)
Vertical: comun
Actor: administrador
Pantalla: Plantillas de Meta
Pasos:
1. Pulsar **Borrar** en la fila.
2. Leer «¿Borrar esta plantilla?» con su nombre y pulsar **Borrar** (o **Cancelar**).
3. La plantilla desaparece de la lista y no se vuelve a traer de Meta.
Entra: la plantilla elegida.
Sale: plantilla borrada aquí (se conserva marcada como borrada); aviso público de plantilla borrada.
Si falla: «No se pudo borrar la plantilla» (o el motivo) encima de la lista.
Implicados: pendiente
Pendiente de enlazar: hub — puerta de plantillas de WhatsApp (borrar en Meta)
QA: ninguno

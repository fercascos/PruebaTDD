/**
 * El castellano → inglés de la interfaz `[REQ]` S-05.
 *
 * La clave es el texto en castellano. El porqué está en `idioma.tsx`.
 *
 * ## El glosario no me lo he inventado
 *
 * `[REQ]` El cliente **ya tiene** un inglés propio para este dominio: está en
 * sus plantillas Modelo A y B inglesas, y en las columnas de su tabla de
 * CAPEX. Traducir «Objeto» por «Object» sería correcto y estaría **mal**,
 * porque en su informe pone `Item`. Las equivalencias que manda su plantilla:
 *
 * | Castellano | Inglés del cliente |
 * |---|---|
 * | Objeto | **Item** |
 * | Zona afectada | **Affected area** |
 * | Concepto | **Purpose** |
 * | Grupo *(grado de riesgo)* | **Group** |
 * | Recuperable | **Recoverable** |
 * | Corto / Medio / Largo plazo | **Short / Mid / Long term** |
 * | Mejoras | **Improvements** |
 * | CAPEX estimado | **Estimated CAPEX** |
 * | Cubierta · Fachadas · Ascensores | **Roof · Facades · Elevators** |
 *
 * `[LIM]` Dos de las suyas no son el inglés que uno escribiría —`ACCESIBILITY`
 * con una `s`, `ELECTRICAL INSTALATION` con una `l`— y **se respetan igual**
 * donde se refieren a la sección de su informe: corregirle la ortografía al
 * cliente en su propio documento no es cosa nuestra. En el texto de la
 * aplicación, que es nuestro, van bien escritas.
 *
 * ## Lo demás del dominio, decidido una vez y aplicado en todas partes
 *
 * | Castellano | Inglés | Por qué |
 * |---|---|---|
 * | hallazgo | **finding** | Es el término del sector; «issue» sugiere avería |
 * | activo | **asset** | El inmueble, no «active» |
 * | proyecto | **project** | El cliente eligió «proyecto» sobre «encargo» (docs/23) |
 * | plazo | **term** | Coherente con Short/Mid/Long term |
 * | fase | **phase** | |
 * | visita | **site visit** | «visit» a secas se confunde con la web |
 * | descriptivo | **description** | Qué hay |
 * | valoración | **assessment** | En qué estado está. Su plantilla pone «Valuation», que en inglés es tasación económica: dentro del informe se respeta, en la aplicación no se usa |
 * | emitir | **issue** | Un informe emitido es inmutable |
 * | ficha | **record** | |
 */
export const EN: Record<string, string> = {
  // ── El marco de la aplicación ─────────────────────────────────────────
  'Due diligence técnica': 'Technical due diligence',
  Proyectos: 'Projects',
  Plantillas: 'Templates',
  Sugerencias: 'Suggestions',
  Personas: 'People',
  Salir: 'Sign out',
  'Sin conexión.': 'Offline.',
  Español: 'Spanish',
  'Idioma de la interfaz': 'Interface language',
  'Puede seguir haciendo fotografías: se guardan en el dispositivo y se suben cuando vuelva la cobertura. Lo demás necesita red y va a fallar.':
    'You can keep taking photos: they are stored on the device and uploaded when coverage returns. Everything else needs a connection and will fail.',

  // ── Entrar y recuperar la contraseña ──────────────────────────────────
  'Acceda con las credenciales de su organización.':
    'Sign in with your organisation credentials.',
  'Correo electrónico': 'Email',
  Contraseña: 'Password',
  'Contraseña nueva': 'New password',
  'Contraseña inicial': 'Initial password',
  'Contraseña cambiada': 'Password changed',
  'Correo o contraseña incorrectos': 'Incorrect email or password',
  'He olvidado mi contraseña': 'I forgot my password',
  'Elegir contraseña nueva': 'Choose a new password',
  'Enviarme el enlace': 'Email me the link',
  'Enlace incompleto': 'Incomplete link',
  'Escriba su correo y le enviaremos un enlace para elegir una contraseña nueva.':
    'Enter your email and we will send you a link to choose a new password.',
  'Recuperando la sesión…': 'Restoring your session…',

  // ── Lista de proyectos ────────────────────────────────────────────────
  'Nuevo proyecto': 'New project',
  'Crear proyecto': 'Create project',
  'Todavía no hay ningún proyecto dado de alta en esta organización.':
    'No projects have been created in this organisation yet.',
  Código: 'Code',
  'Código interno': 'Internal code',
  'Código del cliente': 'Client code',
  Proyecto: 'Project',
  Cliente: 'Client',
  Arranque: 'Start',
  Cierre: 'Close',
  Estado: 'Status',
  'Cambiar estado…': 'Change status…',
  'Escrito al dar de alta; falta validarlo': 'Entered on creation; not yet validated',
  'Datos del proyecto': 'Project details',
  'Campo del proyecto': 'Project field',
  'Director de proyecto': 'Project lead',
  'El compromiso de entrega del informe': 'The agreed report delivery date',
  'Acceso al repositorio del cliente': "Access to the client's repository",

  // ── Resumen del proyecto ──────────────────────────────────────────────
  'Introducción del proyecto': 'Project introduction',
  'Guardar la introducción': 'Save the introduction',
  'Introducción guardada.': 'Introduction saved.',
  'Abre el informe final tal como se escriba aquí':
    'Opens the final report exactly as written here',
  'Alcance del trabajo, tipología de los activos, fechas de visita, limitaciones generales…':
    'Scope of work, asset types, site visit dates, general limitations…',
  'Fases de la due diligence': 'Due diligence phases',
  'Dónde están los activos': 'Where the assets are',
  'Informe final': 'Final report',
  'Defensa del informe': 'Report defence',

  // ── El cuadro de mando ────────────────────────────────────────────────
  'CAPEX del proyecto': 'Project CAPEX',
  'CAPEX del activo': 'Asset CAPEX',
  'Distribución por activo': 'Breakdown by asset',
  'Distribución por concepto de gasto': 'Breakdown by purpose',
  'Distribución por grado de riesgo e importe': 'Breakdown by risk group and amount',
  'Desglose por categoría y objeto': 'Breakdown by category and item',
  'Agrupado por tipo de coste': 'Grouped by cost type',
  'De mayor a menor importe.': 'Highest to lowest amount.',
  'Cada barra es una': 'Each bar is one',
  '% de su categoría': '% of its category',
  'Cuánto del CAPEX recae sobre la propiedad y cuánto es repercutible al inquilino.':
    'How much of the CAPEX falls on the landlord and how much is recoverable from the tenant.',

  // ── Vocabulario del CAPEX · el inglés de SU plantilla ─────────────────
  // `[LIM]` «Comentarios», «Grupo», «Mejoras» y «Otro» **no están aquí** aunque
  // sean del mismo glosario: son columnas de la tabla del informe y viven en
  // el servidor (`reporting/capex_layout.py`), no en ninguna pantalla. Se
  // intentaron meter y la prueba de entradas muertas las echó, que es
  // exactamente para lo que está.
  Objeto: 'Item',
  'Zona afectada': 'Affected area',
  Descripción: 'Description',
  Concepto: 'Purpose',
  Riesgo: 'Risk',
  'Corto plazo': 'Short term',
  'Corto plazo (1-2 años)': 'Short term (1-2 years)',
  'Medio plazo': 'Mid term',
  'Largo plazo': 'Long term',
  Capítulo: 'Chapter',
  Categoría: 'Category',
  categoría: 'category',
  Actuación: 'Action',
  actuación: 'action',
  'Actuación recomendada': 'Recommended action',
  '· actuación recurrente': '· recurring action',
  'Añadir otro plazo (actuación recurrente)': 'Add another term (recurring action)',
  'Añadir plazo': 'Add term',
  'Añadir línea': 'Add line',
  'Código CAPEX': 'CAPEX code',
  'Código retirado': 'Retired code',
  'Base imponible': 'Net amount',
  'Coste directo': 'Direct cost',
  'Costes indirectos': 'Indirect costs',
  'Beneficio industrial (BI)': 'Contractor profit',
  'Con impuesto:': 'With tax:',
  'Cómo se calcula': 'How it is calculated',
  'Cómo se calcula · abrir la cascada': 'How it is calculated · open the breakdown',
  'Clasificación del catálogo: es lo que agrega el informe':
    'Catalogue classification: this is what the report aggregates',
  'Catálogo (código, zona, concepto)': 'Catalogue (code, area, purpose)',

  // ── Activos, visitas e inventario ─────────────────────────────────────
  'Añadir activo': 'Add asset',
  'Crear activo': 'Create asset',
  'Crear hallazgo': 'Create finding',
  'Crear hallazgo desde esta foto': 'Create a finding from this photo',
  Dirección: 'Address',
  'Código postal': 'Postcode',
  'Año de construcción': 'Year built',
  'Año de última reforma': 'Year last refurbished',
  'Año de instalación': 'Year installed',
  Año: 'Year',
  'Altura libre de almacén (m)': 'Warehouse clear height (m)',
  'Altura máxima del edificio (m)': 'Maximum building height (m)',
  'Datos de la visita': 'Site visit details',
  'Coste de la visita': 'Site visit cost',
  'Coste interno del proyecto: NO entra en el CAPEX del edificio ni sale en el informe del cliente':
    "Internal project cost: it does NOT enter the building CAPEX and does not appear in the client's report",
  'Equipo implicado': 'Team involved',
  'Equipo implicado guardado.': 'Team involved saved.',
  'Añadir acompañante': 'Add attendee',
  'Añadir del equipo': 'Add from the team',
  'Añadir equipo': 'Add equipment',
  'Editar equipo': 'Edit equipment',
  'Añadir al inventario': 'Add to the inventory',
  'Añadir una persona del equipo': 'Add a team member',
  'En calidad de…': 'Attending as…',
  'Enfriadora, ascensor, cuadro general…': 'Chiller, lift, main switchboard…',
  'enfriadora, lámina, ascensor…': 'chiller, membrane, lift…',
  'Como está rotulado en la sala: CL-01, AS-Norte…':
    'As labelled on site: CL-01, AS-North…',
  'Agota su vida útil en': 'Reaches the end of its service life in',
  'al día': 'up to date',
  'Dentro de': 'In',
  Después: 'Later',
  'Determina las zonas disponibles al registrar hallazgos':
    'Determines which areas are available when recording findings',
  'Dónde está': 'Where it is',
  'Dónde está exactamente. Alimenta el token [Espacio] al renombrar':
    'Exactly where it is. Feeds the [Space] token when renaming',
  'Dónde se hizo cada fotografía': 'Where each photo was taken',
  'en qué estado está': 'what condition it is in',
  'En qué estado está, qué se ha observado y qué se concluye.':
    'What condition it is in, what was observed and what is concluded.',
  'En qué estado está. Lo escribe quien lo ha visto':
    'What condition it is in. Written by whoever inspected it',

  // ── Documentación y fotografías ───────────────────────────────────────
  Documentación: 'Documentation',
  'Documento solicitado': 'Requested document',
  'Adjuntar documento': 'Attach document',
  'Añadir a la checklist': 'Add to the checklist',
  'Añadir fotografías': 'Add photos',
  'Desde el carrete': 'From the camera roll',
  'Desde el ordenador': 'From this computer',
  'Activo al que asignar lo que se suba': 'Asset to assign the uploads to',
  'Asignar al activo elegido': 'Assign to the selected asset',
  'Es el texto que se inserta bajo la imagen en el PPTX':
    'This is the caption inserted below the image in the PPTX',
  'El original no se toca.': 'The original is never modified.',
  'El árbol acordado con el cliente:': 'The tree agreed with the client:',
  'El documento existe pero está fuera de su plazo de vigencia o de revisión.':
    'The document exists but is outside its validity or review period.',
  'El documento no concuerda consigo mismo.': 'The document contradicts itself.',
  'El documento se declara borrador, resumen o copia sin valor.':
    'The document states that it is a draft, summary or uncontrolled copy.',
  'El documento no ha propuesto ningún dato del edificio. Los avisos de arriba dicen por qué.':
    'The document proposed no building data. The warnings above explain why.',
  ', así que hay que decir en qué activo va: el documento no lo dice.':
    ', so the asset must be stated: the document does not say.',

  // ── Informes ──────────────────────────────────────────────────────────
  'A revisión': 'To review',
  'Comprobar antes de generar': 'Check before generating',
  'Corrija lo bloqueante para generar': 'Fix the blocking items to generate',
  'Emitir (bloquea para siempre)': 'Issue (locks permanently)',
  'Descargar la plantilla': 'Download the template',
  'Descarga la plantilla CAPEX rellena solo con este activo':
    'Downloads the CAPEX template filled in with this asset only',

  // ── Precios ───────────────────────────────────────────────────────────
  'Actualización por índice': 'Index-linked update',
  'Actualizar el precio por un índice': 'Update the price using an index',
  'Buscar entre las registradas': 'Search the recorded references',
  'De dónde sale': 'Where it comes from',
  'Editable: puede no ser el de ninguna referencia':
    'Editable: it need not match any reference',
  'El precio de la impermeabilización está desfasado':
    'The waterproofing price is out of date',
  'ES-MAD, nacional…': 'ES-MAD, national…',
  'Cada cuántos meses': 'Every how many months',
  'Ámbito': 'Scope',
  'Ámbar': 'Amber',

  // ── Sugerencias y personas ────────────────────────────────────────────
  'Bandeja de propuestas': 'Proposals inbox',
  'Enviar propuesta': 'Send proposal',
  'Atiende el buzón de sugerencias': 'Handles the suggestions inbox',
  'Dar de alta': 'Create',
  'Dar de alta a alguien': 'Add someone',
  'Desactivar echa a alguien ahora, no cuando caduque su token de refresco.':
    'Deactivating removes someone now, not when their refresh token expires.',
  'Borrado lógico: los hallazgos ya redactados lo conservan':
    'Soft delete: findings already written keep it',
  'Coincide con lo que ya hay. Aceptarlo no cambia nada.':
    'It matches what is already there. Accepting it changes nothing.',

  // ── Mensajes comunes ──────────────────────────────────────────────────
  Añadir: 'Add',
  'No se ha podido guardar': 'Could not be saved',
  'Esta pantalla ha intentado guardar sin decir sobre qué versión escribe.':
    'This screen tried to save without stating which version it was writing over.',
  'Elegir la hoja…': 'Choose the sheet…',
  'Elegir otra hoja': 'Choose a different sheet',
  'Columnas que no se reconocen y': 'Unrecognised columns, and',
  'El renombrado escribirá «SinSistema»': 'Renaming will write “NoSystem”',
  'al renombrar fotografías.': 'when renaming photos.',
  '— en la raíz —': '— at the root —',
  '— no está en la lista —': '— not on the list —',
  'Es lo que lee el revisor y lo que sale en el informe':
    'This is what the reviewer reads and what goes into the report',
  'Alcance: los': 'Scope: the',

  // ── «Cargando…» · una familia entera, con la misma forma ──────────────
  'Cargando activos…': 'Loading assets…',
  'Cargando el activo…': 'Loading the asset…',
  'Cargando el árbol documental…': 'Loading the document tree…',
  'Cargando el CAPEX del activo…': 'Loading the asset CAPEX…',
  'Cargando el dashboard…': 'Loading the dashboard…',
  'Cargando el inventario…': 'Loading the inventory…',
  'Cargando el mapa…': 'Loading the map…',
  'Cargando el proyecto…': 'Loading the project…',
  'Cargando fases…': 'Loading phases…',
  'Cargando fotografías…': 'Loading photos…',
  'Cargando hallazgos…': 'Loading findings…',
  'Cargando la bandeja…': 'Loading the inbox…',
  'Cargando la documentación…': 'Loading the documentation…',
  'Cargando la fotografía…': 'Loading the photo…',
  'Cargando la matriz…': 'Loading the matrix…',
  'Cargando las visitas…': 'Loading the site visits…',
  'Cargando los activos…': 'Loading the assets…',
  'Cargando los gráficos…': 'Loading the charts…',
  'Cargando personas…': 'Loading people…',
  'Cargando proyectos…': 'Loading projects…',
  'Cargando referencias…': 'Loading references…',
  'Cargando ubicaciones…': 'Loading locations…',

  // ── Documentación del activo y revisión con IA ────────────────────────
  'Revisión de documentación con IA': 'AI document review',
  'Revisar con IA': 'Review with AI',
  'Revisar otra vez': 'Review again',
  Revisión: 'Review',
  Lectura: 'Reading',
  Aceptar: 'Accept',
  Descartar: 'Discard',
  Rechazar: 'Reject',
  'Hoy está vacío: aceptarlo lo rellena.': 'It is empty today: accepting fills it in.',
  'Hoy pone': 'It currently says',
  'Lo que la documentación dice sobre sí misma':
    'What the documentation says about itself',
  'Salen de leer los documentos, no de lo que falta.':
    'These come from reading the documents, not from what is missing.',
  'Medios que declara la documentación': 'Provisions declared by the documentation',
  'Salen del capítulo de medios de autoprotección.':
    'These come from the self-protection provisions chapter.',
  Activo: 'Asset',
  'Revisión cada (meses)': 'Review every (months)',
  'No conforme': 'Non-compliant',
  'Uso principal': 'Main use',
  'Plantas sobre rasante': 'Floors above ground',
  'Plantas bajo rasante': 'Floors below ground',
  'Retirar la autorización': 'Withdraw the authorisation',
  'Qué hay que pedir (p. ej. «Licencia de actividad»)':
    'What to request (e.g. “Operating licence”)',
  'Para marcar «no disponible» hace falta decir por qué: es lo que explica la limitación en el informe.':
    'To mark something “not available” you must say why: that is what explains the limitation in the report.',
  'Volver a extraer': 'Extract again',
  'Extraer datos': 'Extract data',
  'Fuera de plazo': 'Out of date',
  'Le faltan datos que el propio documento reserva un sitio para llevar.':
    'It is missing data that the document itself leaves room for.',
  'No vigente': 'Not current',
  'La declara el documento': 'Declared by the document',
  'La escribió quien redactó el documento. Se recoge literal, sin reescribirla.':
    'Written by whoever drafted the document. Recorded verbatim, not rewritten.',
  'Se contradice': 'Contradicts itself',
  'sin sistema técnico': 'no technical system',

  // ── Inventario de equipo ──────────────────────────────────────────────
  'Nuevo equipo': 'New equipment',
  'Guardar equipo': 'Save equipment',
  'Importar desde Excel': 'Import from Excel',
  Identificación: 'Identification',
  'Fabricante y modelo': 'Manufacturer and model',
  'Fabricante, modelo, número de serie…': 'Manufacturer, model, serial number…',
  'Nº de serie': 'Serial no.',
  'Número de serie': 'Serial number',
  Instalado: 'Installed',
  Mantenimiento: 'Maintenance',
  'Mantenimiento preventivo': 'Preventive maintenance',
  'Última revisión': 'Last service',
  'sin última revisión': 'no last service',
  'Trimestral 3, semestral 6, anual 12, quinquenal 60':
    'Quarterly 3, half-yearly 6, annual 12, five-yearly 60',
  Obsolescencia: 'Obsolescence',
  Criticidad: 'Criticality',
  Editar: 'Edit',
  'Sistema técnico': 'Technical system',
  'Vida útil esperada (años)': 'Expected service life (years)',
  'Estado de conservación': 'Condition',
  'Muy deficiente': 'Very poor',
  'Fuera de servicio': 'Out of service',
  'Próximo a obsoleto': 'Approaching obsolescence',
  'Sin repuestos': 'No spare parts',
  'Qué pasa si se para': 'What happens if it stops',
  'Solo los que han agotado su vida útil': 'Only those past their service life',
  'Solo los que tienen el mantenimiento vencido': 'Only those with maintenance overdue',
  'La vida residual se calcula: rellene el año de instalación y la vida útil esperada.':
    'Remaining life is calculated: fill in the year installed and the expected service life.',
  'Se recalcula sola cada año: no se guarda.':
    'It recalculates itself every year: it is not stored.',
  'Hay documentación del equipo (manual, ficha técnica, contrato de mantenimiento)':
    'Equipment documentation exists (manual, data sheet, maintenance contract)',
  'No es lo mismo que el estado: un equipo bien conservado puede no tener repuestos':
    'Not the same as condition: well-kept equipment may still have no spare parts',
  'Se conserva en la base: la ficha se escribió en una visita a la que no se vuelve':
    'Kept in the database: the record was written during a site visit that will not be repeated',

  // ── Precios ───────────────────────────────────────────────────────────
  'Referencias de precio': 'Price references',
  'Introducir precio manual': 'Enter a price manually',
  'Introducir un precio a mano': 'Enter a price by hand',
  'Registrar referencia': 'Record a reference',
  'No hay búsqueda en proveedores externos: la aplicación no consulta ninguno.':
    'There is no search against external suppliers: the application queries none.',
  Elegir: 'Choose',
  Fuente: 'Source',
  'Fuentes no consultadas': 'Sources not consulted',
  'Precio unitario': 'Unit price',
  'Precio que se aplicará': 'Price that will be applied',
  Unidad: 'Unit',
  'Fecha del precio': 'Price date',
  Registrada: 'Recorded',
  Impuestos: 'Taxes',
  Instalación: 'Installation',
  Incluye: 'Includes',
  Excluye: 'Excludes',
  'Importe (€)': 'Amount (€)',
  Justificación: 'Justification',
  'Obligatoria: el importe difiere de la referencia':
    'Required: the amount differs from the reference',
  'Opcional cuando el importe es el de la referencia':
    'Optional when the amount matches the reference',
  'Oferta en firme del proveedor, incluye puesta en marcha…':
    'Firm supplier quote, commissioning included…',
  'Oferta adjunta, catálogo, llamada al fabricante…':
    'Quote attached, catalogue, call to the manufacturer…',
  'Validar precio': 'Validate price',
  'Índice en la fecha del precio': 'Index at the price date',
  'Índice hoy': 'Index today',
  'Factor geográfico': 'Location factor',

  // ── Inventario del activo · descriptivo y valoración ──────────────────
  'Inventario del activo': 'Asset inventory',
  'Inventario relacionado': 'Related inventory',
  'qué hay': 'what is there',
  'Traer descriptivos de la documentación': 'Pull descriptions from the documentation',
  'No se les ha puesto uno automáticamente': 'None was assigned automatically',
  Etiqueta: 'Label',
  Equipo: 'Equipment',
  Sistema: 'System',
  'Objeto del árbol': 'Tree item',
  Descriptivo: 'Description',
  'Qué hay. Dato de documento, no de observación':
    'What is there. Taken from a document, not from observation',
  Valoración: 'Assessment',
  valoración: 'assessment',
  'Validado por un técnico': 'Validated by an engineer',
  'extracción SIMULADA: léalo en el documento antes de validarlo':
    'SIMULATED extraction: read it in the document before validating',
  'Pasa a CAPEX': 'Goes to CAPEX',
  'Vida residual': 'Remaining life',
  'Fotografías de este objeto': 'Photos of this item',
  'No se ha podido completar': 'Could not be completed',
  vacío: 'empty',
  'Qué hay: tipo, cantidad, características. Sale de la memoria técnica.':
    'What is there: type, quantity, characteristics. Taken from the technical report.',
  'Mientras no se marque, el informe lo da por sin validar':
    'Until it is ticked, the report treats it as not validated',

  // ── Visita al activo ──────────────────────────────────────────────────
  'Visita al activo': 'Site visit',
  'Programar una visita': 'Schedule a site visit',
  'Guardar la visita': 'Save the site visit',
  'Visita creada. Ponga la fecha y quién va.':
    'Site visit created. Set the date and who is attending.',
  'Visita guardada.': 'Site visit saved.',
  'Estado de la visita': 'Site visit status',
  'Todavía no hay nadie apuntado a esta visita.': 'Nobody is signed up to this visit yet.',
  'Guardar el equipo': 'Save the team',
  Fotografías: 'Photos',
  fotografía: 'photo',
  fotografías: 'photos',
  'Este activo todavía no tiene fotografías.': 'This asset has no photos yet.',
  'Pendiente de definir': 'To be defined',
  'Sin fecha': 'No date',
  'Fecha prevista': 'Planned date',
  'Fecha real': 'Actual date',
  'La que fecha el informe. Si la deja en blanco, se pone la de hoy al guardar':
    "This is the date on the report. Leave it blank and today's date is used on save",
  'Ubicación y punto de encuentro': 'Location and meeting point',
  'Por dónde se entra y con quién se queda. La dirección del edificio está en su ficha':
    "Where to get in and who to meet. The building address is on the asset's record",
  'Limitaciones de acceso': 'Access limitations',
  'Lo que no se pudo ver. Sale en el informe: «no se accedió a la cubierta» cambia lo que se puede afirmar sobre ella':
    'What could not be inspected. It appears in the report: “the roof was not accessed” changes what can be stated about it',
  'Resumen de la visita': 'Site visit summary',

  // ── Ficha de hallazgo ─────────────────────────────────────────────────
  'Líneas de CAPEX': 'CAPEX lines',
  'Guardar línea': 'Save line',
  'Una actuación recurrente lleva': 'A recurring action has',
  'una línea por plazo': 'one line per term',
  'Mejoras potenciales': 'Potential improvements',
  Título: 'Title',
  'Lo que se observa. Es lo que va al informe':
    'What was observed. This is what goes into the report',
  'Notas internas del equipo': 'Internal team notes',
  Recomendación: 'Recommendation',
  'Grado de riesgo': 'Risk group',
  'Sin precio': 'No price',
  'Pendiente de validación': 'Pending validation',
  'Sin procedencia registrada.': 'No source recorded.',
  'Sin transiciones desde este estado.': 'No transitions available from this status.',
  'Los botones que no se pueden pulsar salen deshabilitados':
    'Buttons that cannot be used are shown disabled',
  'Recargar con los cambios de la otra persona': "Reload with the other person's changes",
  'Trasladar la base calculada al importe': 'Carry the calculated base into the amount',
  'Sustituye el importe por la base calculada. No ocurre solo':
    'Replaces the amount with the calculated base. It does not happen on its own',
  'Ver referencias y validar el precio': 'See references and validate the price',
  'Puede quedar en blanco y rellenarse después': 'It can be left blank and filled in later',

  // ── Ficha de activo ───────────────────────────────────────────────────
  'Nuevo activo': 'New asset',
  'Guardar cambios': 'Save changes',
  Tipología: 'Asset type',
  'no aplican a esta tipología · lo que escriba se conserva igualmente':
    'do not apply to this asset type · anything you enter is kept anyway',
  'No puede ser anterior al de construcción': 'It cannot be earlier than the year built',
  'Superficie de parcela (m²)': 'Plot area (m²)',
  'Superficie construida total (m²)': 'Total built area (m²)',
  'Superficie alquilable (m²)': 'Lettable area (m²)',
  'Superficie de almacén (m²)': 'Warehouse area (m²)',
  'Superficie de oficinas (m²)': 'Office area (m²)',
  'Superficie urbanizada (m²)': 'Developed area (m²)',
  'Superficie útil total (m²)': 'Total usable area (m²)',
  'Ocupación (m²)': 'Footprint (m²)',
  'Lo que el edificio ocupa en la parcela': 'The area the building occupies on the plot',
  'Referencia catastral': 'Land registry reference',
  'Fecha del proyecto': 'Design date',
  'Uso secundario': 'Secondary use',
  'Muelles de carga': 'Loading docks',
  'Plazas de aparcamiento': 'Parking spaces',

  // ── Fotografías ───────────────────────────────────────────────────────
  'Llegó como': 'Arrived as',
  Origen: 'Origin',
  'Fecha de captura': 'Date taken',
  Coordenadas: 'Coordinates',
  Dimensiones: 'Dimensions',
  Huella: 'Fingerprint',
  'Incluir en el informe': 'Include in the report',
  'Seleccionada para el informe pero sin activo: no se sabría en qué diapositiva colocarla.':
    'Selected for the report but with no asset: there would be no way to know which slide it goes on.',
  'Sin pie de foto: saldrá en el informe sin texto debajo.':
    'No caption: it will appear in the report with no text below it.',
  Anotar: 'Annotate',
  Cerrar: 'Close',
  'Este activo no tiene árbol de ubicaciones todavía':
    'This asset has no location tree yet',
  'Nombre visible': 'Display name',
  'Sin extensión: la fija el servidor': 'No extension: the server sets it',
  'Pie de foto': 'Caption',
  'Separadas por comas': 'Comma separated',
  'Orden de aparición': 'Order of appearance',

  // ── Alta de proyecto ──────────────────────────────────────────────────
  'Nombre del proyecto': 'Project name',
  'Se genera al crear · 2026-NNN': 'Generated on creation · 2026-NNN',
  'Lo asigna la aplicación al crear el proyecto. Único e inalterable':
    'Assigned by the application when the project is created. Unique and unchangeable',
  'Fases aplicables': 'Applicable phases',
  'Solicitud de documentación': 'Document request',
  'Visita a los activos': 'Site visits',
  'Red Flag / CAPEX': 'Red Flag / CAPEX',
  'Informe completo': 'Full report',
  'Presentación al cliente': 'Client presentation',
  'Si no está en la lista, escríbalo': 'If it is not on the list, type it',
  'No bloquea: el proyecto se crea y el administrador recibe el aviso para validarlo':
    'It does not block: the project is created and the administrator is notified to validate it',
  'TDD Cartera Norte': 'TDD Northern Portfolio',
  'Inversora Ficticia S.L.': 'Fictitious Investments Ltd.',
  'Fecha de arranque': 'Start date',
  'Fecha de cierre prevista': 'Planned close date',
  'Fecha de entrega prevista': 'Planned delivery date',

  // ── Cuadro de mando ───────────────────────────────────────────────────
  Hallazgos: 'Findings',
  'Reparto de la inversión por pagador': 'Investment split by payer',
  'Perfil temporal de la inversión': 'Investment profile over time',
  'Exposición por grado de riesgo': 'Exposure by risk group',
  'Este bloque no se filtra nunca': 'This block is never filtered',
  'Pulse una barra para incorporar ese activo a la selección o retirarlo de ella.':
    'Click a bar to add that asset to the selection or remove it.',
  'línea de CAPEX': 'CAPEX line',
  'líneas de CAPEX': 'CAPEX lines',
  línea: 'line',
  líneas: 'lines',
  'Todavía no hay ninguna línea de CAPEX valorada.': 'No CAPEX line has been priced yet.',
  'Reparto del CAPEX del proyecto por concepto de gasto':
    'Project CAPEX split by purpose',
  'Reparto del CAPEX del proyecto entre propiedad e inquilinos':
    'Project CAPEX split between landlord and tenants',
  'Quién lo paga': 'Who pays',
  'Sin detallar': 'Not broken down',

  // ── Sugerencias ───────────────────────────────────────────────────────
  'Proponer un cambio': 'Propose a change',
  'Mis propuestas': 'My proposals',
  'Todavía no ha propuesto ningún cambio.': 'You have not proposed any change yet.',
  'No hay propuestas pendientes.': 'There are no pending proposals.',
  'Precio de referencia': 'Reference price',
  'Plantilla de informe': 'Report template',
  'La propia aplicación': 'The application itself',
  'Pasar a revisión': 'Move to review',
  'Marcar duplicada': 'Mark as duplicate',
  'Marcar aplicada': 'Mark as applied',
  'Rechazar una propuesta exige explicar por qué: lo lee quien la escribió':
    'Rejecting a proposal requires an explanation: whoever wrote it will read it',
  'No se ha podido resolver': 'Could not be resolved',
  'Nota de respuesta (obligatoria al rechazar)': 'Reply note (required when rejecting)',
  Explicación: 'Explanation',
  'Qué cambiaría y por qué': 'What you would change and why',

  // ── Calculadora de CAPEX ──────────────────────────────────────────────
  Calcular: 'Calculate',
  Sobre: 'On',
  Importe: 'Amount',
  Medición: 'Measurement',
  'Precio unitario (€)': 'Unit price (€)',
  'Gastos generales (GG)': 'Overheads',
  'Honorarios técnicos': 'Professional fees',
  Impuesto: 'Tax',
  'Total con impuesto': 'Total including tax',
  'Usar la base imponible como importe': 'Use the net amount as the amount',
  'Fracción: 0,21 para el 21 %': 'Fraction: 0.21 for 21 %',
  'Porcentajes de la convención española, y': 'Percentages follow Spanish practice, and',
  'PEM · directo + indirectos': 'Works cost · direct + indirect',
  'PEC · PEM + GG + BI': 'Contract cost · works cost + overheads + profit',

  // ── Plantillas de informe ─────────────────────────────────────────────
  'Plantillas de informe': 'Report templates',
  'Subir una plantilla PPTX': 'Upload a PPTX template',
  'No hay ninguna plantilla registrada todavía.': 'No template has been registered yet.',
  'No se ha podido subir la plantilla': 'The template could not be uploaded',
  Diapositivas: 'Slides',
  Marcadores: 'Placeholders',
  'Marcador de la plantilla': 'Template placeholder',
  Avisos: 'Warnings',
  'lleva marca de agua · se retirará al generar':
    'has a watermark · it will be removed when generating',
  Mapear: 'Map',
  Mapeo: 'Mapping',
  'Nombre del mapeo': 'Mapping name',
  'Mapeo guardado.': 'Mapping saved.',
  'Guardar mapeo': 'Save mapping',
  Estándar: 'Standard',

  // ── Importar inventario ───────────────────────────────────────────────
  'Importar inventario desde Excel': 'Import inventory from Excel',
  'Leyendo la hoja…': 'Reading the sheet…',
  'La hoja no tiene filas con datos.': 'The sheet has no rows with data.',
  Fila: 'Row',
  'Qué pasa': 'What happens',
  Observaciones: 'Notes',
  'Volver al inventario': 'Back to the inventory',
  'Se creará': 'Will be created',
  'Ya existe': 'Already exists',
  'Repetida en la hoja': 'Duplicated in the sheet',
  'Tipo de equipo': 'Equipment type',
  'Vida útil': 'Service life',
  'Ningún fichero elegido': 'No file chosen',

  // ── Informes ──────────────────────────────────────────────────────────
  'Generar informe': 'Generate report',
  'No hay ninguna plantilla registrada. Súbala en «Plantillas» antes de generar un informe.':
    'No template is registered. Upload one under “Templates” before generating a report.',
  Versiones: 'Versions',
  Versión: 'Version',
  'Todavía no se ha generado ningún informe de este proyecto.':
    'No report has been generated for this project yet.',
  'Huella del PPTX': 'PPTX fingerprint',
  'Generando… se actualiza solo': 'Generating… it refreshes by itself',
  'No se pudo generar. Vuelva a pedirlo; si se repite, avise a soporte.':
    'It could not be generated. Try again; if it happens again, contact support.',
  Aprobar: 'Approve',
  'No se ha podido comprobar': 'It could not be checked',
  'No se ha podido generar': 'It could not be generated',
  'No se ha podido cambiar el estado': 'The status could not be changed',

  // ── CAPEX del proyecto y exportación ──────────────────────────────────
  'Registrar hallazgo': 'Record a finding',
  Idioma: 'Language',
  English: 'English',
  Alcance: 'Scope',
  'Un libro por activo': 'One workbook per asset',
  'Un libro para todo el proyecto': 'One workbook for the whole project',
  'Un libro por activo, cada uno con su cabecera y sus zonas, en un ZIP':
    'One workbook per asset, each with its own header and areas, in a ZIP',
  'Exportar este activo': 'Export this asset',
  'Exportar por activo (ZIP)': 'Export per asset (ZIP)',
  'Exportar a XLSX': 'Export to XLSX',
  'Sin activo en el proyecto': 'No asset in the project',
  'Rellena la plantilla CAPEX del cliente y la descarga':
    "Fills in the client's CAPEX template and downloads it",

  // ── Nuevo hallazgo ────────────────────────────────────────────────────
  'Nuevo hallazgo': 'New finding',
  'Nuevo hallazgo desde la fotografía': 'New finding from the photo',
  'Hereda el activo y la zona de la fotografía, y la deja enlazada como evidencia.':
    'It inherits the asset and area from the photo, and links the photo as evidence.',
  'Título de la actuación': 'Action title',
  'Renovación de impermeabilización': 'Waterproofing renewal',
  'Una línea por plazo. El importe que teclee': 'One line per term. The amount you enter',
  Quitar: 'Remove',
  'Mejora potencial': 'Potential improvement',
  'Otro tipo de petición': 'Other type of request',
  'Solo las que admite la tipología del activo': 'Only those allowed by the asset type',

  // ── Fotografías del proyecto ──────────────────────────────────────────
  'Sin asignar (se avisa, no se bloquea)': 'Unassigned (it warns, it does not block)',
  'Sistema técnico de lo que se suba': 'Technical system for whatever is uploaded',
  'Sin clasificar': 'Unclassified',
  'Ver solo las de': 'Show only those from',
  'Todos los activos': 'All assets',
  'Todos los sistemas': 'All systems',
  'Solo las seleccionadas para el informe': 'Only those selected for the report',
  'Quitar del informe': 'Remove from the report',
  'Ninguna fotografía cumple el filtro.': 'No photo matches the filter.',
  'Todavía no hay fotografías. Use los botones de arriba para añadirlas.':
    'There are no photos yet. Use the buttons above to add some.',

  // ── Personas ──────────────────────────────────────────────────────────
  'Nueva persona': 'New person',
  'No hay nadie más en la organización.': 'There is nobody else in the organisation.',
  Nombre: 'Name',
  'Nombre y apellidos': 'Full name',
  Correo: 'Email',
  Rol: 'Role',
  Acciones: 'Actions',
  'Técnico especialista': 'Specialist engineer',
  'Mínimo 12 caracteres. Comuníquela por un canal aparte; quien entre debería cambiarla':
    'At least 12 characters. Send it through a separate channel; whoever signs in should change it',

  // ── Anotador y renombrado de fotografías ──────────────────────────────
  Cancelar: 'Cancel',
  Deshacer: 'Undo',
  Limpiar: 'Clear',
  Trazo: 'Stroke',
  Línea: 'Line',
  'Texto de la anotación': 'Annotation text',
  'No se ha podido cargar la fotografía': 'The photo could not be loaded',
  'Renombrar en lote…': 'Rename in bulk…',
  Plantilla: 'Template',
  Previsualizar: 'Preview',
  Antes: 'Before',
  'Numerar correlativamente desde 001': 'Number consecutively from 001',

  // ── Subida de fotografías ─────────────────────────────────────────────
  'Hacer una foto': 'Take a photo',
  'Subirlas ahora': 'Upload them now',
  Quedaron: 'Left over',
  'Fallo de red': 'Network error',
  'No se suben solas: la decisión de gastar datos es suya':
    'They are not uploaded automatically: spending mobile data is your call',
  'No se pudo abrir IndexedDB': 'IndexedDB could not be opened',
  'Transacción rechazada': 'Transaction rejected',

  // ── Árbol de CAPEX y de ubicaciones ───────────────────────────────────
  Total: 'Total',
  'Total del nodo': 'Node total',
  Repercutible: 'Recoverable',
  'N. A.': 'N/A',
  'Ubicaciones del edificio': 'Building locations',
  'Nombre de la ubicación': 'Location name',
  'Nombre (p. ej. «Sala Máquinas 2»)': 'Name (e.g. “Plant Room 2”)',
  Eliminar: 'Delete',

  // ── Documentación del activo ──────────────────────────────────────────
  Adjuntar: 'Attach',
  'No aplica': 'Not applicable',
  'No disponible': 'Not available',
  'Pendiente de pedir': 'Not yet requested',
  'Recibida en parte': 'Partly received',
  'Por qué no está disponible': 'Why it is not available',
  'Marcar «no disponible» exige decir por qué: es lo que explica la limitación en el informe.':
    'Marking something “not available” requires a reason: that is what explains the limitation in the report.',

  // ── Pestañas del proyecto y del activo ────────────────────────────────
  Resumen: 'Summary',
  Activos: 'Assets',
  Dashboard: 'Dashboard',
  Riesgos: 'Risks',
  'Ficha de cada equipo': 'Record for each item of equipment',
  'Fotografías de la visita': 'Site visit photos',
  Abrir: 'Open',
  Borrar: 'Delete',
  Ciudad: 'City',
  'Superficie construida': 'Built area',
  'No se ha podido borrar': 'It could not be deleted',
  'Este proyecto todavía no tiene activos.': 'This project has no assets yet.',
  'Este proyecto todavía no tiene activos. Un proyecto sin activos no sale de borrador.':
    'This project has no assets yet. A project without assets cannot leave draft.',
  'Este activo no tiene coordenadas. Se ponen en su ficha, a mano o proponiéndolas desde la dirección.':
    'This asset has no coordinates. They are set on its record, by hand or proposed from the address.',
  'Ningún activo tiene coordenadas todavía. Se ponen en la ficha de cada uno.':
    'No asset has coordinates yet. They are set on each asset record.',
  Todos: 'All',
  'Uno, varios o ninguno. Sin ninguna casilla marcada se lee la cartera entera.':
    'One, several or none. With no box ticked the whole portfolio is shown.',

  // ── Fases y riesgos ───────────────────────────────────────────────────
  'Este proyecto no tiene ninguna fase activa. Las fases se eligen a la carta al darlo de alta.':
    'This project has no active phase. Phases are chosen individually when the project is created.',
  'La aplicación deduce que debería estar en': 'The application infers it should be in',
  'Se calcula del trabajo hecho: no se marca a mano':
    'Derived from the work done: it is not set by hand',
  Grado: 'Grade',
  'Riesgo por capítulo': 'Risk by chapter',
  'Riesgo × horizonte temporal': 'Risk × time horizon',

  // ── Recuperar el acceso ───────────────────────────────────────────────
  Entrar: 'Sign in',
  'Volver a entrar': 'Back to sign in',
  'Recuperar el acceso': 'Recover access',
  'Guardar la contraseña': 'Save the password',
  Repítala: 'Repeat it',
  'Las dos contraseñas no coinciden.': 'The two passwords do not match.',
  'Pedir un enlace nuevo': 'Request a new link',

  // ── Conflictos de edición ─────────────────────────────────────────────
  'Recargue y vuelva a intentarlo; si se repite, es un fallo de la aplicación.':
    'Reload and try again; if it happens again, it is an application bug.',

  // ── Los trozos de frase que conviven con una etiqueta ─────────────────
  //
  // `[REQ]` La tercera tanda, y la que obligó a cambiar de herramienta. Son
  // los pedazos de texto que comparten párrafo con un `<strong>`, un `<code>`
  // o un enlace:
  //
  //     <p className="ayuda">
  //       El árbol del cliente, y dentro de cada objeto lo que se sabe de él:{' '}
  //       <strong>Descriptivo</strong>, que sale de la memoria técnica.
  //     </p>
  //
  // Son TRES nodos de texto, y un extractor por expresión regular no ve
  // ninguno: la regla que exige el párrafo entero limpio los descarta, y la
  // que acepta «todo lo que hay entre > y <» recoge además el código —en
  // `useState<Foo>()` el genérico abre y cierra igual—, trescientos falsos
  // positivos. Se cambió a leerlo con el parser de TypeScript, que no se
  // equivoca porque un nodo de texto JSX lo es por definición del lenguaje.
  //
  // Se traducen trozo a trozo y la frase inglesa conserva la estructura de la
  // castellana. `[LIM]` Vale para «prosa, término, prosa», que es lo que hay
  // aquí; no valdría para un idioma que exigiera mover el término de sitio.

  '(Descriptivo, que sale de la memoria técnica) y':
    '(Description, which comes from the technical report) and',
  '(Valoración, que la escribe quien lo ha visto), con sus equipos y sus fotografías. Las categorías nacen plegadas; se abren solas las que ya tienen trabajo hecho.':
    '(Assessment, written by whoever has seen it), with their equipment and their photos. Categories start collapsed; those with work already done open on their own.',
  '). Explique por qué.': '). Explain why.',
  ', así que la redacta una persona y no se genera sola.':
    ', so a person writes it and it is not generated on its own.',
  ', de mayor a menor. Un hallazgo codificado en la propia categoría, sin descender al objeto, figura como «sin detallar»: no es lo mismo que un objeto denominado «General».':
    ', largest first. A finding coded against the category itself, without going down to the item, shows as «not broken down»: that is not the same as an item named «General».',
  ': distribución por concepto de gasto, perfil temporal, exposición por riesgo, categoría con sus objetos y activo.':
    ': breakdown by purpose of spend, timing profile, exposure by risk, category with its items, and asset.',
  ': es la referencia contra la que se lee el resto. Los activos sin actuaciones se muestran con cero: uno que desaparece de la lista se confunde con uno que se visitó y no tenía nada.':
    ': it is the benchmark the rest is read against. Assets with no actions are shown as zero: one that vanishes from the list looks the same as one that was inspected and had nothing.',
  ': es una casilla sin rellenar —depende de los contratos de arrendamiento y se decide actuación por actuación—, y por eso va en gris y no con un color de serie.':
    ': it is an unfilled box —it depends on the lease agreements and is decided action by action— which is why it is grey and not a series colour.',
  ': indirectos, honorarios y contingencia ya dentro. La aplicación nunca aplica la cascada por encima. Añada otra línea solo si la actuación es':
    ': indirect costs, fees and contingency already included. The application never applies the cascade on top. Add another line only if the action is',
  ': nadie ha leído este documento. Lo de abajo ocupa el sitio de lo que vendrá y no dice nada sobre su contenido.':
    ': nobody has read this document. What follows stands in for what will come and says nothing about its contents.',
  ': no hay fuente de precios externa, así que esta parte se ajusta a mano hasta que la haya.':
    ': there is no external price source, so this part is adjusted by hand until there is one.',
  ': un capítulo tiene once objetos y elegir por usted sería adivinar dónde está la máquina. Colóquelos y dejarán de estar aquí —y su actuación sabrá dónde ir.':
    ': a chapter has eleven items and choosing for you would mean guessing where the machine is. Place them and they will stop appearing here —and their action will know where to go.',
  'Aceptar crea la ficha de equipo': 'Accepting creates the equipment record',
  'Actualizar los': 'Update the',
  'Alcance: un solo activo ·': 'Scope: a single asset ·',
  'Aplicar a': 'Apply to',
  'Autorizada para este proyecto': 'Authorised for this project',
  'Buscar': 'Search',
  'Cantidad': 'Quantity',
  'Clasificar en': 'Classify under',
  'Comentarios': 'Comments',
  'Datos de la memoria técnica': 'Technical report data',
  'Datos de nave': 'Warehouse unit data',
  'Dónde está cada cosa dentro de este activo. Es distinto de la zona: la zona clasifica para el informe («Cubierta»), esto localiza para volver a encontrarlo («Cubierta › Sala Máquinas 2»). Lo que se elija aquí alimenta el token':
    'Where each thing is inside this asset. It is different from the area: the area classifies for the report («Roof»), this locates it so it can be found again («Roof › Plant Room 2»). What is chosen here feeds the token',
  'El desglose económico está en el': 'The financial breakdown is in the',
  'El importe no coincide con la referencia elegida (':
    'The amount does not match the chosen reference (',
  'El importe se ha tecleado; no está respaldado por ninguna referencia.':
    'The amount was typed in; it is not backed by any reference.',
  'El libro tiene': 'The workbook has',
  'El árbol del cliente, categoría a categoría, y dentro de cada objeto lo que se sabe de él:':
    'The client\'s tree, category by category, and inside each item what is known about it:',
  'Equipos sin objeto (': 'Equipment with no item (',
  'Espacio': 'Location',
  'Esto crea una versión nueva con la capa encima; el fichero de la cámara sigue igual y las anotaciones se pueden volver a editar. Se queman sobre la imagen solo al generar el informe.':
    'This creates a new version with the layer on top; the camera file stays as it is and the annotations can be edited again. They are burned onto the image only when the report is generated.',
  'Etiquetas': 'Tags',
  'Fabricante': 'Manufacturer',
  'Faltan columnas obligatorias:': 'Required columns are missing:',
  'Generar actuaciones de los marcados (': 'Generate actions for the ticked ones (',
  'Guardar el inventario': 'Save the inventory',
  'Hay': 'There are',
  'La información básica: qué se compra, para quién, con qué alcance se revisa y qué queda fuera.':
    'The basics: what is being bought, for whom, the scope of the review and what is left out.',
  'Llevar': 'Move to',
  'Mapeo de «': 'Mapping of «',
  'Modelo': 'Model',
  'Motivo': 'Reason',
  'Naturaleza de la inversión. Es la distinción que separa un activo caro de uno mal mantenido:':
    'The nature of the spend. It is the distinction that separates an expensive asset from a badly maintained one:',
  'No se pudo revisar:': 'Could not be reviewed:',
  'No son imágenes y se han dejado fuera:': 'These are not images and have been left out:',
  'Plazo': 'Term',
  'Promotor': 'Developer',
  'Quién puede entrar y con qué rol. La matriz completa de permisos está en':
    'Who can sign in and with which role. The full permissions matrix is in',
  'Recibida el': 'Received on',
  'Reintentar las': 'Retry the',
  'Renombrar': 'Rename',
  'Se crean solo las que marque. Un proyecto sin Q&A no arrastra una fase vacía que nadie va a rellenar. Las marcadas como':
    'Only the ones you tick are created. A project with no Q&A does not carry an empty phase nobody is going to fill in. Those marked as',
  'Se dieron de alta antes de que el inventario preguntara de qué objeto cuelga cada equipo.':
    'They were created before the inventory started asking which item each piece of equipment hangs off.',
  'Sin cartografía de fondo: no hay proveedor de teselas configurado, así que la aplicación no contacta con ningún servidor externo. Las posiciones y las distancias son correctas —use la escala—. Para ver el mapa, defina':
    'No background mapping: no tile provider is configured, so the application contacts no external server. The positions and distances are correct —use the scale bar—. To see the map, set',
  'Solo las aceptadas entran en el apartado de limitaciones del informe':
    'Only those accepted go into the limitations section of the report',
  'Tipo': 'Type',
  'Ver': 'View',
  'Ver los': 'View the',
  'Zona': 'Area',
  '`[REQ]` P-41 · El permiso es separable del rol para que alguien pueda atender el buzón':
    '`[REQ]` P-41 · The permission is separable from the role so that somebody can handle the inbox',
  'añadido(s) al inventario': 'added to the inventory',
  'base calculada por medición:': 'base calculated from the measurement:',
  'bloquean la generación': 'block generation',
  'del árbol de CAPEX y los tramos de dentro son sus':
    'of the CAPEX tree and the bands inside are its',
  'descartada(s), con constancia de quién fue': 'discarded, with a record of who did so',
  'documento(s) sin línea de checklist': 'document(s) with no checklist line',
  'equipo(s) han agotado su vida útil esperada. Es una estimación a partir del año de instalación, no un dictamen: un equipo con mantenimiento puede seguir dando servicio.':
    'item(s) of equipment have exhausted their expected service life. That is an estimate from the year of installation, not a verdict: a maintained unit may well keep working.',
  'etiqueta(s) leídas que no se han sabido encajar': 'tag(s) read that could not be matched',
  'fotografías no llevan coordenadas y no salen aquí. En un sótano no hay señal, y muchos móviles van con la localización apagada. No se infiere ninguna posición: si no vino en el EXIF, no está.':
    'photos carry no coordinates and do not appear here. There is no signal in a basement, and many phones run with location switched off. No position is inferred: if it did not come in the EXIF, it is not there.',
  'fotografías sin subir de una sesión anterior. Siguen guardadas en este dispositivo.':
    'photos not yet uploaded from an earlier session. They are still stored on this device.',
  'líneas con precio sin validar, por': 'lines with an unvalidated price, totalling',
  'marcadores sin origen. Si se genera así, saldrían literalmente en el documento: la generación lo impide.':
    'tokens with no source. Generated like this they would appear literally in the document: generation prevents it.',
  'no se marcan a mano después: su estado sale del trabajo que hay debajo.':
    'are not ticked by hand afterwards: their state comes from the work underneath.',
  'nombres coincidían y han recibido un sufijo alfabético (_b, _c…) para no pisarse.':
    'names clashed and have been given an alphabetic suffix (_b, _c…) so they do not overwrite each other.',
  'objetos en tabla, con su categoría': 'items in a table, with their category',
  'página': 'page',
  'revisiones de este documento. Se muestra la más reciente.':
    'reviews of this document. The most recent one is shown.',
  '· su activo se borró después de registrarlos. Siguen contando en el total.':
    '· their asset was deleted after they were recorded. They still count towards the total.',
  '—hace falta ahora y otra vez más adelante—, que es lo que P-44 permite.':
    '—needed now and again later on—, which is what P-44 allows.',

  // ── El estado de un proyecto ──────────────────────────────────────────
  //
  // `[REQ]` La pantalla enseñaba el código del enumerado —«BORRADOR»,
  // «VISITA_PROGRAMADA»—, que en inglés no dice nada. Los rótulos están en
  // `ui/estados.ts`; aquí va su inglés.
  'En preparación': 'In preparation',
  'Visita programada': 'Inspection scheduled',
  'Visita realizada': 'Inspection completed',
  'En análisis': 'Under analysis',
  'En revisión': 'Under review',
  'Informe emitido': 'Report issued',

  // ── El texto de ayuda, que ocupa varias líneas ────────────────────────
  //
  // Son los párrafos de los `<p className="ayuda">`: lo que explica una
  // pantalla a quien la usa por primera vez, y la mitad del valor de esta
  // aplicación para alguien de negocio.
  //
  // `[REQ]` Estaban SIN TRADUCIR y el extractor decía que no faltaba nada: su
  // regla de texto JSX excluía el salto de línea a propósito —para no cruzar
  // etiquetas— y un párrafo que el formateador parte en cuatro renglones
  // quedaba invisible. Sesenta y siete nodos, cincuenta y cuatro de ellos con
  // texto suelto. No lo encontró leer el código: lo encontró abrir el
  // prototipo en inglés y ver los párrafos en castellano.

  'Apagada. Ningún documento de este proyecto se analiza mientras lo esté. La autoriza quien dirige el proyecto, y queda constancia de quién lo hizo.':
    'Off. No document in this project is analysed while it stays off. The project director authorises it, and a record is kept of who did so.',
  'Cuánta de la inversión corresponde a cada grado, del más severo al menos. Los grados sin importe se muestran con cero: uno que desaparece de la lista se confunde con uno que no tiene nada.':
    'How much of the spend falls under each grade, most severe first. Grades with no amount are shown as zero: one that vanishes from the list looks the same as one with nothing in it.',
  'Cuánto dinero hay en cada cruce de gravedad y plazo. Responde a «¿cuánto de lo grave hay que pagar en los dos primeros años?».':
    'How much money sits at each intersection of severity and term. It answers «how much of the serious work has to be paid for in the first two years?».',
  'El año de instalación y la vida útil esperada van juntos o no van: con solo uno de los dos no hay vida residual que calcular.':
    'The year of installation and the expected service life go together or not at all: with only one of the two there is no remaining life to calculate.',
  'El catálogo del CAPEX no tiene objetos cargados, así que no hay árbol que recorrer. Siembre los catálogos y vuelva a entrar.':
    'The CAPEX catalogue has no items loaded, so there is no tree to walk. Seed the catalogues and come back.',
  'El detalle completo: fabricante, número de serie, mantenimiento preventivo y vida residual, que se calcula al leer y nunca se teclea.':
    'The full detail: manufacturer, serial number, planned maintenance and remaining life, which is calculated on reading and never typed in.',
  'El enlace caduca a los 30 minutos y solo sirve una vez. Al terminar se cerrarán todas sus sesiones abiertas.':
    'The link expires after 30 minutes and works once. When you finish, every open session of yours will be closed.',
  'El grado nunca se identifica solo por color: cada fila lleva su código y su nombre escritos. Los importes son los del CAPEX del proyecto; lo descartado no suma.':
    'The grade is never identified by colour alone: every row carries its code and its name in writing. The amounts are the project\'s CAPEX; what has been discarded does not count.',
  'El proyecto todavía no tiene activos. Un equipo cuelga siempre de uno: dé de alta el edificio primero.':
    'The project has no assets yet. A piece of equipment always hangs off one: create the building first.',
  'Elija una referencia. Un precio conserva siempre su procedencia: si el importe no sale de ninguna de las registradas, dé de alta una manual con su origen.':
    'Choose a reference. A price always keeps its provenance: if the amount comes from none of those on record, create a manual one stating where it came from.',
  'En un proyecto de cartera es la cifra que entra en la negociación de cada activo.':
    'In a portfolio project this is the figure that goes into the negotiation for each asset.',
  'Esta casilla entra en las limitaciones del informe: declarar lo que no se ha podido revisar es una obligación profesional en una TDD.':
    'This item goes into the limitations of the report: stating what could not be reviewed is a professional obligation in a technical due diligence.',
  'Esta línea entra en las limitaciones del informe: declarar lo que no se ha podido revisar es una obligación profesional en una TDD.':
    'This line goes into the limitations of the report: stating what could not be reviewed is a professional obligation in a technical due diligence.',
  'Estas actuaciones están codificadas en códigos que ya no se ofrecen. Siguen contando en los totales —por eso salen aquí y no desaparecen—, pero conviene recodificarlas: al exportar, la plantilla no sabe en qué bloque ponerlas.':
    'These actions are coded against codes that are no longer offered. They still count towards the totals —which is why they appear here rather than vanishing— but they are worth recoding: on export, the template does not know which block to put them in.',
  'Este activo no tiene ninguna visita registrada. Se puede programar antes de tener fecha: la visita nace «pendiente de definir» y no obliga a inventarse un día.':
    'This asset has no inspection on record. One can be set up before there is a date: the inspection starts out «to be confirmed» and does not force anyone to invent a day.',
  'Este activo no tiene ubicaciones. Sin ellas las fotografías se pueden clasificar por zona, pero no se puede decir en qué sala estaban.':
    'This asset has no locations. Without them photos can be classified by area, but there is no way to say which room they were taken in.',
  'Este activo todavía no tiene actuaciones. Se registran desde «Hallazgos y CAPEX», desde una fotografía de la visita, o aquí mismo cuando el árbol tenga ramas.':
    'This asset has no actions yet. They are recorded from «Findings and CAPEX», from a photo taken during the inspection, or right here once the tree has branches.',
  'Este enlace no lleva el código de recuperación. Suele pasar al copiarlo a mano desde el correo: ábralo pulsando sobre él, o pida uno nuevo.':
    'This link carries no recovery code. That usually happens when it is copied by hand from the email: open it by clicking on it, or request a new one.',
  'Este navegador no garantiza guardar las fotografías pendientes: puede borrarlas si el dispositivo se queda sin espacio, y en un iPhone también tras varios días sin abrir la aplicación. Añádala a la pantalla de inicio, o súbalas antes de cerrar.':
    'This browser gives no guarantee that pending photos will be kept: it may delete them if the device runs out of space, and on an iPhone also after several days without opening the application. Add it to your home screen, or upload them before closing.',
  'Este objeto no tiene equipos inventariados. No siempre hace falta: una cubierta o una fachada se describen y se valoran, pero no tienen máquinas que fichar.':
    'This item has no equipment on the inventory. It is not always needed: a roof or a facade is described and assessed, but has no machines to record.',
  'Este proyecto no tiene ningún activo dado de alta todavía, y un equipo tiene que nacer en alguno. Créalo antes de aceptar estas propuestas.':
    'This project has no asset created yet, and a piece of equipment has to be born in one. Create it before accepting these proposals.',
  'Estos campos se guardan siempre. Reclasificar el activo no los borra: si mañana vuelve a ser una nave, la altura de almacén sigue ahí.':
    'These fields are always kept. Reclassifying the asset does not delete them: if tomorrow it becomes a warehouse unit again, the warehouse height is still there.',
  'Habilitar una fuente exige registrar la revisión de sus condiciones de uso y requiere rol de administrador.':
    'Enabling a source requires recording a review of its terms of use, and an administrator role.',
  'La checklist está vacía. Añade arriba lo que hay que pedir: cada línea que quede sin recibir se convierte sola en una limitación del informe.':
    'The checklist is empty. Add above what needs requesting: every line left unreceived turns into a limitation of the report on its own.',
  'La próxima revisión se calcula: no se teclea. Un documento puede declarar que hay revisiones «anuales o quinquenales según el tipo de equipo» sin decir cuál le toca a cuál, y en ese caso esto se queda vacío hasta que alguien lo sepa.':
    'The next service is calculated, not typed in. A document may state that there are «annual or five-yearly» services «depending on the type of equipment» without saying which applies to which, and in that case this stays empty until somebody knows.',
  'Las de este activo. Se suben desde «Fotografías», también desde el móvil durante la visita, y se atan a cada equipo desde el inventario.':
    'Those for this asset. They are uploaded from «Photos», including from a phone during the inspection, and tied to each piece of equipment from the inventory.',
  'Llegaron al proyecto sin decir qué solicitud cubren. Se pueden revisar igual, pero no cuentan para la checklist ni para las limitaciones del informe.':
    'They reached the project without saying which request they cover. They can still be reviewed, but they do not count towards the checklist or the limitations of the report.',
  'Lleva dentro los activos de este proyecto y los 14 sistemas técnicos. Rellenarla a partir de ella evita que media hoja falle por una tilde en el nombre del edificio.':
    'It already contains this project\'s assets and the 14 technical systems. Filling it in from this copy stops half the sheet failing over an accent in the building\'s name.',
  'Marcadores disponibles: [Proyecto] [ProyectoNombre] [Activo] [Sistema] [Zona] [Espacio] [Capitulo] [Categoria] [Fecha] [Hora] [Numero] [Autor] [Etiqueta]. La extensión no forma parte de la plantilla: la fija el servidor desde el tipo real del archivo.':
    'Available tokens: [Proyecto] [ProyectoNombre] [Activo] [Sistema] [Zona] [Espacio] [Capitulo] [Categoria] [Fecha] [Hora] [Numero] [Autor] [Etiqueta]. The file extension is not part of the pattern: the server sets it from the file\'s real type.',
  'Ninguna fotografía de esta selección trae coordenadas. Se registran solas si el móvil tiene la localización activada al hacer la foto.':
    'No photo in this selection carries coordinates. They are recorded automatically if location is switched on when the photo is taken.',
  'No hay catálogo de índices en la aplicación: los dos valores los introduce usted. Publicar una cifra que nadie ha verificado sería inventar una fuente de precios.':
    'There is no index catalogue in the application: you enter both values. Publishing a figure nobody has verified would mean inventing a price source.',
  'No hay ninguna referencia registrada que encaje. Introduzca el precio a mano indicando de dónde sale.':
    'No reference on record matches. Enter the price by hand, stating where it comes from.',
  'No se ha aplicado nada todavía, y aplicarlo solo rellena el campo: sigue haciendo falta validar el precio.':
    'Nothing has been applied yet, and applying it only fills the field: the price still needs validating.',
  'Por horizonte de ejecución, en orden de plazo y no de importe: lo que se lee aquí es el escalonamiento del desembolso, y reordenarlo por cuantía lo destruiría.':
    'By delivery horizon, ordered by term and not by amount: what you read here is how the spend is staged, and reordering it by size would destroy that.',
  'Proponga cambios en precios, catálogos, textos o plantillas. Las propuestas las atiende un administrador; usted ve siempre las suyas.':
    'Propose changes to prices, catalogues, wording or templates. An administrator handles the proposals; you can always see your own.',
  'Queda firmado con su usuario y con la fecha. Es lo que permite preguntar de dónde salió dentro de seis meses.':
    'It is signed with your user and the date. That is what makes it possible to ask where it came from six months later.',
  'Quién fue. Del equipo se elige de la lista de personas; quien acompaña —el jefe de mantenimiento, el mantenedor de PCI— se escribe, porque no tiene cuenta en la aplicación.':
    'Who attended. Team members are picked from the list of people; those accompanying —the maintenance manager, the fire-protection contractor— are typed in, because they have no account in the application.',
  'Salen de la memoria técnica del edificio. Mientras ponga «sin validar», nadie ha revisado que sean correctos: un dato leído de un documento no es lo mismo que uno tecleado por un técnico.':
    'They come from the building\'s technical report. While it says «not validated», nobody has checked that they are correct: a figure read from a document is not the same as one typed in by an engineer.',
  'Se analiza al subirla: si tiene problemas, se descubren ahora y no cuando alguien esté esperando un informe.':
    'It is analysed on upload: if there are problems, they come to light now and not while somebody is waiting for a report.',
  'Sin equipos en el inventario. Es opcional: un proyecto se entrega igual sin él. Sirve para apuntar en la visita el fabricante, el modelo y el año de lo que después se propone sustituir.':
    'No equipment on the inventory. It is optional: a project is delivered just the same without it. It is there to note down, during the inspection, the manufacturer, model and year of whatever is later proposed for replacement.',
  'Sin hallazgos registrados todavía. No es lo mismo que no tener CAPEX: puede que aún no se haya visitado.':
    'No findings recorded yet. That is not the same as having no CAPEX: it may simply not have been inspected.',
  'Solo un administrador puede dar de alta o modificar cuentas. Aquí las ve, pero no las cambia: la API lo rechaza igualmente con un 403.':
    'Only an administrator can create or change accounts. You can see them here but not change them: the API rejects it with a 403 regardless.',
  'Sus fichas se sobrescribirán. Si alguien las corrigió a mano después de la visita, esos cambios se pierden.':
    'Their records will be overwritten. If somebody corrected them by hand after the inspection, those changes are lost.',
  'También vale una hoja propia: se reconocen varios nombres para cada columna, y las que no se entiendan se enumeran antes de importar en vez de perderse.':
    'Your own sheet works too: several names are recognised for each column, and any that are not understood are listed before importing rather than quietly lost.',
  'Tipo de coste → categoría → objeto. Solo se dibujan las ramas que tienen algo: el catálogo trae 175 nodos y un activo toca unos pocos.':
    'Cost type → category → item. Only the branches with something in them are drawn: the catalogue carries 175 nodes and an asset touches a handful.',
  'Todas las de la organización. Este listado solo lo ve quien atiende el buzón, y no porque esta pantalla lo esconda: la base de datos no devuelve las filas.':
    'All of the organisation\'s. Only whoever handles the inbox sees this list, and not because this screen hides it: the database does not return the rows.',
  'Todavía no hay hallazgos que clasificar. La matriz se rellena sola a medida que se registran.':
    'There are no findings to classify yet. The matrix fills itself in as they are recorded.',
  'Todavía no hay hallazgos. En campo también se crean desde la propia fotografía, que hereda el activo y la zona.':
    'No findings yet. In the field they can also be created straight from a photo, which inherits the asset and the area.',
  'Todavía no hay ninguna línea de CAPEX valorada. Este dashboard se rellena solo a medida que se registran hallazgos con su importe.':
    'No CAPEX line has been priced yet. This dashboard fills itself in as findings are recorded with their amounts.',
  'Todavía no hay ninguna. Salen solas al atar una fotografía de la visita a uno de estos equipos, o al clasificarla en este objeto.':
    'There are none yet. They appear on their own when a photo from the inspection is tied to one of these units, or classified under this item.',
  'Todavía sin importe. Es válido: en campo se anota lo que se ve antes de saber cuánto cuesta.':
    'No amount yet. That is valid: in the field you write down what you see before knowing what it costs.',
  'Todos los del proyecto en el mismo mapa: dos naves en el mismo polígono y una oficina a treinta kilómetros no se gestionan igual.':
    'All of the project\'s on one map: two units on the same estate and an office thirty kilometres away are not managed the same way.',
  'Ya puede entrar con la contraseña nueva. Se han cerrado todas las sesiones que hubiera abiertas, también en otros dispositivos.':
    'You can now sign in with the new password. Every session that was open has been closed, including on other devices.',
  '`[REC]` Lo correcto sería una invitación por correo. Exige SMTP y no está montado, así que de momento la fija quien da de alta. No se disimula que es un apaño.':
    '`[REC]` The right way would be an email invitation. That needs SMTP, which is not set up, so for now whoever creates the account sets the password. No pretence that this is anything but a stopgap.',

  // ── Rótulos que estaban en la lógica ──────────────────────────────────
  //
  // No son una pantalla: son las cadenas que vivían dentro de la lógica —el
  // gerundio de un botón ocupado, el singular y el plural de un recuento, el
  // hueco de un título con el nombre de alguien dentro— y que el cableado
  // automático no podía distinguir de un nombre de ruta o de un valor de
  // enumerado. Se repasaron a mano, una por una.
  //
  // Los gerundios van con «…» igual que en castellano: es el mismo gesto —el
  // botón está ocupado y se queda quieto— y el cliente lo usa así en sus
  // propias pantallas.
  'Analizando…': 'Analysing…',
  'Entrando…': 'Signing in…',
  'Enviando…': 'Sending…',
  'Guardando…': 'Saving…',
  'Leyendo…': 'Reading…',
  'Preparando…': 'Preparing…',
  'Revisando…': 'Reviewing…',
  'Subiendo…': 'Uploading…',
  'Validando…': 'Validating…',

  // Recuentos. Singular y plural como dos entradas, que es lo que hay: dos
  // idiomas con la misma regla de plural y ninguna necesidad de una
  // biblioteca para resolverla.
  hallazgo: 'finding',
  hallazgos: 'findings',
  actuaciones: 'actions',
  conceptos: 'purposes',
  pagadores: 'payers',

  // Mantenimiento.
  'sin plan': 'no schedule',
  vencido: 'overdue',

  Autorizar: 'Authorise',

  // Títulos y frases con un hueco. El hueco se resuelve **después** de
  // traducir, así que la frase inglesa puede colocarlo donde le toque.
  'CAPEX de {quien}': 'CAPEX for {quien}',
  'Editar «{nombre}»': 'Edit “{nombre}”',
  'Reparto del CAPEX de {quien} por concepto de gasto':
    'CAPEX breakdown for {quien} by purpose of spend',
  'Reparto del CAPEX de {quien} entre propiedad e inquilinos':
    'CAPEX breakdown for {quien} between landlord and tenants',
  '«{quien}» no tiene ninguna línea de CAPEX valorada. No es lo mismo que no tener hallazgos: puede tenerlos sin importe.':
    '“{quien}” has no priced CAPEX line. That is not the same as having no findings: it may have findings with no amount.',
  Guardar: 'Save',
  alguien: 'someone',
  'Guardar {cuantas} anotaciones': 'Save {cuantas} annotations',
  'Precio: {estado}': 'Price: {estado}',
  'Añadir actuación en {nodo}': 'Add action under {nodo}',
  'Añadir actuación en {nodo} ({codigo})': 'Add action under {nodo} ({codigo})',
  '{creados} descriptivo(s) nuevo(s), {completados} completado(s) y {respetados} respetado(s) porque ya tenían texto o estaban validados. Las valoraciones no se tocan: no salen de ningún documento.':
    '{creados} new description(s), {completados} completed and {respetados} left alone because they already had text or were validated. Assessments are never touched: they come from no document.',
}

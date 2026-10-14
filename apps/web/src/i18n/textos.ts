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
  'Las valoraciones no se tocan: no salen de ningún documento.':
    'Assessments are never touched: they come from no document.',
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
}

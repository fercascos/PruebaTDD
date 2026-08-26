/** Los tipos que devuelve la API. Se escriben a mano y a propósito: generarlos
 *  del OpenAPI produciría nombres impronunciables y arrastraría cada cambio del
 *  backend a la interfaz sin filtro. */

export type Perfil = {
  id: string
  organization_id: string
  email: string
  full_name: string
  org_role: string
  /** La marca de la ficha. Para decidir en la interfaz use `gestiona_sugerencias`. */
  can_manage_suggestions: boolean
  /** El permiso efectivo sobre el buzón, tal como lo calcula el servidor. */
  gestiona_sugerencias: boolean
}

export type Proyecto = {
  id: string
  internal_code: string
  name: string
  status: string
  currency: string
}

export type Fase = {
  id: string
  code: string
  name_es: string
  status: string
  es_derivado: boolean
  detalle: string
  display_order: number
  estado_sugerido: string | null
}

export type Activo = {
  id: string
  project_id: string
  typology_id: string
  name: string
  asset_code: string | null
  city: string | null
  year_built: number | null
  total_built_sqm: string | null
  main_photo_id: string | null
}

export type ElementoCatalogo = { id: string; code: string; name_es: string }

export type Duplicado = {
  tipo: 'EXACTO' | 'CASI'
  photo_id: string
  distancia: number
  display_name: string
  mensaje: string
}

export type Foto = {
  id: string
  project_id: string
  asset_id: string | null
  zone_id: string | null
  /**
   * `[REQ]` §10 · La ubicación física concreta dentro del edificio. Alimenta el
   * token `[Espacio]`, que era el último del renombrado en lote que se omitía
   * siempre porque el árbol no existía.
   */
  location_node_id: string | null
  /** `[REQ]` §3.2 · Alimenta el token `[Sistema]` del renombrado en lote. */
  technical_system_id: string | null
  status: string
  origin: string
  original_filename: string
  display_name: string
  file_extension: string
  sha256: string
  byte_size: number
  width_px: number | null
  height_px: number | null
  taken_at: string | null
  gps_latitude: number | null
  gps_longitude: number | null
  caption: string | null
  tags: string[]
  include_in_report: boolean
  report_order: number | null
  duplicado?: Duplicado | null
  avisos?: string[]
}

export type LineaCapex = {
  id: string
  time_horizon_code: string
  amount: string
  tax_pct: string
  tax_amount: string
  total_cost: string
  price_status: string
  computed_base: string | null
  /** `[REQ]` §14 · La referencia contra la que se validó, si se validó. */
  selected_price_reference_id: string | null
  price_reference_label: string | null
  price_validation_note: string | null
  /**
   * La versión **de la línea**, no la del hallazgo. Es la que hay que mandar
   * al editarla: editar una línea no toca la fila del hallazgo, así que su
   * versión no detectaría que otra persona cambió esta misma línea.
   */
  row_version: number
}

export type Hallazgo = {
  id: string
  project_id: string
  asset_id: string
  zone_id: string
  capex_code_id: string
  title: string
  description: string
  comments: string | null
  recommendation: string | null
  status: string
  risk_level_id: string | null
  capex_lines: LineaCapex[]
  total_amount: string
  total_with_tax: string
  /**
   * `[REQ]` La versión sobre la que se escribe. La API la exige en `If-Match`
   * para modificar o borrar un hallazgo: sin ella responde `428`.
   */
  row_version: number
}

export type Destino = { to: string; allowed: boolean; blockers: string[] }

export type Plantilla = {
  id: string
  name: string
  language: string
  sha256: string
  slide_count: number | null
  analysis: { placeholders: string[]; has_watermark: boolean; fonts: string[] } | null
  is_active: boolean
}

export type Mapeo = {
  id: string
  template_id: string
  name: string
  bindings: Record<string, string>
  is_default: boolean
}

export type AvisoDeInforme = {
  codigo: string
  severidad: 'BLOQUEANTE' | 'ALTA' | 'MEDIA' | 'BAJA'
  mensaje: string
  entidad: string | null
  entidad_id: string | null
  bloquea: boolean
}

export type Previo = {
  can_generate: boolean
  blockers: string[]
  summary: { total: number; blocking: number; by_severity: Record<string, number> }
  warnings: AvisoDeInforme[]
}

export type VersionDeInforme = {
  id: string
  project_id: string
  version_number: number
  status: string
  pptx_sha256: string | null
  data_snapshot_sha256: string
  warnings: AvisoDeInforme[]
  is_locked: boolean
  supersedes_version_id: string | null
}

export type SistemaTecnico = {
  id: string
  code: string
  name_es: string
  /** `[REQ]` §5.8 · Texto, no clave: «Protección contra incendios» → «H06 + H10». */
  capex_chapter: string | null
}

export type Equipo = {
  id: string
  project_id: string
  asset_id: string
  technical_system_id: string | null
  technical_system_name: string | null
  zone_id: string | null
  zone_name: string | null
  tag: string | null
  equipment_type: string
  manufacturer: string | null
  model: string | null
  serial_number: string | null
  install_year: number | null
  expected_life_years: number | null
  condition: string | null
  obsolescence: string | null
  criticality: string | null
  quantity: string
  unit: string
  has_documentation: boolean
  notes: string | null
  /** `[REQ]` P-15 · Todo lo de abajo lo CALCULA el servidor al leer. No se guarda
   *  ni se teclea: una vida residual almacenada mentiría a partir del 1 de enero. */
  end_of_life_year: number | null
  remaining_life_years: number | null
  vencido: boolean
  horizonte_code: string | null
  horizonte_name: string | null
  vida_resumen: string
}

export type FilaImportada = {
  /** Número de fila tal como se ve en Excel: decir «fila 3» y que sea la 3. */
  fila: number
  estado: 'NUEVA' | 'YA_EXISTE' | 'DUPLICADA_EN_FICHERO' | 'ERROR'
  errores: string[]
  avisos: string[]
  crudo: Record<string, string>
  existente_id: string | null
}

export type Previsualizacion = {
  resumen: string
  hoja: string
  /** `[LIM]` Solo se lee la primera hoja del libro. */
  total_hojas: number
  columnas_ignoradas: string[]
  columnas_ausentes: string[]
  filas: FilaImportada[]
  nuevas: number
  ya_existen: number
  con_error: number
  aviso: string
}

export type ResultadoImportacion = {
  creados: number
  actualizados: number
  omitidos: number
  resumen: string
  previsualizacion: Previsualizacion
}

// ─────────────────────────────────────────────────────────────────────────────
//  Solicitud de documentación y su revisión con IA
// ─────────────────────────────────────────────────────────────────────────────

export type EstadoSolicitud = 'SOLICITADA' | 'RECIBIDA' | 'PARCIAL' | 'NO_DISPONIBLE' | 'NO_APLICA'

export type Solicitud = {
  id: string
  category_id: string
  category_name: string
  asset_id: string | null
  title: string
  description: string | null
  status: EstadoSolicitud
  unavailable_reason: string | null
  requested_at: string | null
  received_at: string | null
  /** Columna generada: `PARCIAL` y `NO_DISPONIBLE` alimentan las limitaciones. */
  affects_report_limitations: boolean
  display_order: number
}

export type CategoriaDeSolicitud = { id: string; code: string; name_es: string }

export type Documento = {
  id: string
  project_id: string
  asset_id: string | null
  doc_request_item_id: string | null
  qa_round_id: string | null
  original_filename: string
  display_name: string
  file_extension: string
  mime_type: string
  sha256: string
  byte_size: number
  doc_type: string
  confidentiality: string
  status: string
  version_number: number
  supersedes_document_id: string | null
  notes: string | null
  uploaded_by: string
}

/** `[REQ]` Autorización expresa por encargo, con constancia de quién la dio. */
export type PermisoDeRevision = { activo: boolean; desde: string | null; por: string | null }

export type VeredictoIa = 'CONFORME' | 'NO_CONFORME' | 'FALTA' | 'DUDOSO'
export type DecisionIa = 'PROPUESTA' | 'ACEPTADA' | 'RECHAZADA'

export type ObservacionIa = {
  id: string
  check_code: string
  check_name: string
  verdict: VeredictoIa
  summary: string
  evidence_text: string | null
  evidence_page: number | null
  confidence: number | null
  decision: DecisionIa
  decided_by: string | null
  decision_note: string | null
}

export type RevisionIa = {
  id: string
  document_id: string
  status: 'PENDIENTE' | 'EN_CURSO' | 'COMPLETADA' | 'FALLIDA' | 'CANCELADA'
  provider: string
  model: string | null
  /** Si es cierto, ningún proveedor ha leído el documento. */
  is_simulated: boolean
  document_sha256: string
  error_message: string | null
  observaciones: ObservacionIa[]
}

export type CriterioDeRevision = { code: string; name_es: string; description_es: string }


// ─────────────────────────────────────────────────────────────────────────────
//  El árbol físico del activo (§8.4)
// ─────────────────────────────────────────────────────────────────────────────

export type TipoDeNodo = 'ZONA' | 'PLANTA' | 'ESPACIO'

/**
 * Un nodo del árbol de ubicaciones.
 *
 * `zone` clasifica —«Cubierta», y con eso se agrega en el informe—; esto
 * localiza —«Cubierta › Sala Máquinas 2», y con eso se vuelve a encontrar algo
 * seis meses después—. Son cosas distintas y las dos hacen falta.
 */
export type NodoDeUbicacion = {
  id: string
  asset_id: string
  parent_id: string | null
  node_type: TipoDeNodo
  zone_id: string | null
  zone_name: string | null
  code: string | null
  name: string
  level_order: number
  /** Cuántos antepasados tiene. La pantalla sangra con esto, sin recorrer nada. */
  profundidad: number
  /** «Cubierta › Sala Máquinas 2», ya armada por la API. */
  ruta_legible: string
}

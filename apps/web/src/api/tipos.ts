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

export type Vector = 'AGUA' | 'ELECTRICIDAD' | 'GAS' | 'RESIDUOS'

export interface Yo {
  id: string
  email: string
  nombre: string
  rol: string
  organizacion_id: string
  organizacion: string
  ve_todo: boolean
  escribe_datos: boolean
  escribe_estructura: boolean
}

export interface Cobertura {
  dias_esperados: number
  dias_con_dato: number
  porcentaje: string | null
  lecturas_sin_normalizar: number
}

export interface Total {
  vector: Vector
  unidad: string
  medido: string
  estimado: string
  variacion_porcentual: string | null
  cobertura: Cobertura
}

export interface PuntoDeSerie {
  vector: Vector
  mes: string
  cantidad: string
}

export interface Intensidad {
  vector: Vector
  por_m2: string | null
  por_ocupante: string | null
}

export interface ActivoDelPanel {
  activo_id: string
  codigo: string
  nombre: string
  cartera_id: string
  superficie_m2: string | null
  superficie_de_referencia: string
  ocupantes_medios: string | null
  totales: Total[]
  intensidades: Intensidad[]
}

export interface Panel {
  desde: string
  hasta: string
  totales: Total[]
  serie: PuntoDeSerie[]
  activos: ActivoDelPanel[]
}

export interface Cartera {
  id: string
  nombre: string
  codigo: string
  cliente_id: string | null
  cliente: string | null
  superficie_de_referencia: string
  activos: number
}

export interface Activo {
  id: string
  cartera_id: string
  cartera: string
  codigo: string
  nombre: string
  municipio: string | null
  tipologia: string
  superficie_m2: string | null
  superficie_de_referencia: string
  suministros: number
}

export interface Incidencia {
  fila: number | null
  columna: string | null
  codigo: string
  mensaje: string
  valor: string | null
}

export interface ResultadoDeCarga {
  carga_id: string | null
  aplicada: boolean
  filas_totales: number
  filas_aceptadas: number
  filas_rechazadas: number
  filas_sin_normalizar: number
  ya_cargado_antes: boolean
  mapeo: { columnas: Record<string, string>; faltan: string[]; avisos: string[] } | null
  incidencias: Incidencia[]
}

export interface LecturaPendiente {
  id: string
  activo: string
  suministro: string
  vector: Vector
  inicio: string
  fin: string
  cantidad: string
  unidad: string
  confianza: string | null
  nota: string | null
}

export interface ResultadoImportacion {
  carga_id: string
  facturas_leidas: number
  confirmadas: number
  pendientes_de_revision: number
  rechazadas: number
  incidencias: Incidencia[]
}

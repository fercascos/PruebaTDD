import { useRef, useState } from 'react'
import { descargar, subirFichero } from '../api/cliente'
import type { Previsualizacion, ResultadoImportacion } from '../api/tipos'
import { Mensaje, Vacio } from '../ui/Marco'

const ETIQUETA: Record<string, string> = {
  NUEVA: 'Se creará',
  YA_EXISTE: 'Ya existe',
  DUPLICADA_EN_FICHERO: 'Repetida en la hoja',
  ERROR: 'Error',
}

const COLUMNAS: [string, string][] = [
  ['asset', 'Activo'],
  ['tag', 'Etiqueta'],
  ['equipment_type', 'Tipo de equipo'],
  ['technical_system', 'Sistema'],
  ['manufacturer', 'Fabricante'],
  ['install_year', 'Instalado'],
  ['expected_life_years', 'Vida útil'],
]

/**
 * Importación del inventario desde XLSX `[REQ]` §7.
 *
 * El equipo vive en Excel: el inventario de una nave con instalaciones llega
 * en una hoja que alguien rellenó durante la visita, no fila a fila en un
 * formulario.
 *
 * **Dos pasos, no uno.** Se sube, se lee lo que va a pasar fila a fila, y
 * aplicar es otro botón. Una importación que mete trescientas filas y luego
 * informa de que doce dieron error obliga a limpiar a mano lo que ya entró.
 *
 * **Nada se sobrescribe solo.** Las filas cuya etiqueta ya está en ese activo
 * salen marcadas y se omiten. Actualizarlas es una casilla que hay que marcar:
 * la ficha que hay en la base la escribió alguien en una visita a la que no se
 * vuelve, y puede llevar correcciones posteriores a la hoja.
 */
export function ImportarInventario({
  projectId,
  alTerminar,
  alCerrar,
}: {
  projectId: string
  alTerminar: () => void
  alCerrar: () => void
}) {
  const [fichero, setFichero] = useState<File | null>(null)
  const [previa, setPrevia] = useState<Previsualizacion | null>(null)
  const [resultado, setResultado] = useState<ResultadoImportacion | null>(null)
  const [actualizar, setActualizar] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const entrada = useRef<HTMLInputElement>(null)

  async function elegir(elegido: File | null) {
    setFichero(elegido)
    setPrevia(null)
    setResultado(null)
    setError(null)
    if (!elegido) return
    setOcupado(true)
    try {
      setPrevia(
        await subirFichero<Previsualizacion>(
          `/projects/${projectId}/equipment/import/preview`,
          elegido,
        ),
      )
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setOcupado(false)
    }
  }

  async function aplicar() {
    if (!fichero) return
    setOcupado(true)
    setError(null)
    try {
      // Se reenvía el fichero: el servidor vuelve a analizarlo en vez de fiarse
      // de lo previsualizado. Entre una cosa y otra pueden pasar minutos y otra
      // persona puede haber dado de alta el mismo equipo.
      setResultado(
        await subirFichero<ResultadoImportacion>(`/projects/${projectId}/equipment/import`, fichero, {
          confirmar: 'true',
          actualizar_existentes: actualizar ? 'true' : 'false',
        }),
      )
      alTerminar()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setOcupado(false)
    }
  }

  const vista = resultado?.previsualizacion ?? previa

  return (
    <div className="importar">
      <div className="titular">
        <h2>Importar inventario desde Excel</h2>
        <button type="button" className="secundario" onClick={alCerrar}>
          Cerrar
        </button>
      </div>

      {error && <Mensaje tipo="error">{error}</Mensaje>}

      <section>
        <h3>1 · La plantilla</h3>
        <p className="ayuda">
          Lleva dentro los activos de este encargo y los 14 sistemas técnicos. Rellenarla a partir
          de ella evita que media hoja falle por una tilde en el nombre del edificio.
        </p>
        <button
          type="button"
          className="secundario"
          onClick={() =>
            void descargar(
              `/projects/${projectId}/equipment/import/plantilla.xlsx`,
              'inventario-plantilla.xlsx',
            )
          }
        >
          Descargar la plantilla
        </button>
        <p className="ayuda">
          También vale una hoja propia: se reconocen varios nombres para cada columna, y las que no
          se entiendan se enumeran antes de importar en vez de perderse.
        </p>
      </section>

      <section>
        <h3>2 · Subir la hoja</h3>
        {/* El control nativo de fichero rotula su botón en el idioma del
            navegador —«Choose File»—, y esta aplicación está enteramente en
            español. Se oculta y se dispara desde un botón propio; el `input`
            sigue existiendo, así que el teclado y los lectores de pantalla
            funcionan igual. */}
        <input
          ref={entrada}
          id="hoja-de-inventario"
          type="file"
          className="oculto-visual"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          onChange={(e) => void elegir(e.target.files?.[0] ?? null)}
        />
        <div className="selector-de-fichero">
          <button type="button" className="secundario" onClick={() => entrada.current?.click()}>
            {fichero ? 'Elegir otra hoja' : 'Elegir la hoja…'}
          </button>
          <label htmlFor="hoja-de-inventario">{fichero ? fichero.name : 'Ningún fichero elegido'}</label>
        </div>
        {ocupado && !resultado && <p className="cargando">Leyendo la hoja…</p>}
      </section>

      {vista && (
        <section>
          <h3>3 · Qué va a pasar</h3>

          {resultado ? (
            <Mensaje tipo="ok">{resultado.resumen}</Mensaje>
          ) : (
            <Mensaje tipo="aviso">{vista.aviso}</Mensaje>
          )}

          <p className="recuento">
            <strong>{vista.resumen}</strong>
            {vista.total_hojas > 1 && (
              <>
                {' · '}
                <span className="ayuda">
                  El libro tiene {vista.total_hojas} hojas y solo se lee «{vista.hoja}».
                </span>
              </>
            )}
          </p>

          {vista.columnas_ausentes.length > 0 && (
            <Mensaje tipo="error">
              Faltan columnas obligatorias: {vista.columnas_ausentes.join(', ')}. Sin ellas no hay
              nada que importar.
            </Mensaje>
          )}

          {/* Enumerar lo que no se ha entendido es deliberado: una columna
              «Nº serie» mal escrita perdería el dato sin que nadie se enterase
              hasta buscarlo meses después. */}
          {vista.columnas_ignoradas.length > 0 && (
            <Mensaje tipo="aviso">
              Columnas que no se reconocen y <strong>no se importan</strong>:{' '}
              {vista.columnas_ignoradas.join(', ')}.
            </Mensaje>
          )}

          {vista.filas.length === 0 ? (
            <Vacio>La hoja no tiene filas con datos.</Vacio>
          ) : (
            <div className="desbordable">
              <table className="tabla previa-importacion">
                <thead>
                  <tr>
                    <th scope="col">Fila</th>
                    <th scope="col">Qué pasa</th>
                    {COLUMNAS.map(([, titulo]) => (
                      <th key={titulo} scope="col">
                        {titulo}
                      </th>
                    ))}
                    <th scope="col">Observaciones</th>
                  </tr>
                </thead>
                <tbody>
                  {vista.filas.map((f) => (
                    <tr key={f.fila} className={`e-${f.estado.toLowerCase()}`}>
                      <td className="numerica">{f.fila}</td>
                      {/* El estado va escrito, no solo en color: esto se
                          revisa a veces impreso y uno de cada doce hombres es
                          daltónico. */}
                      <td>{ETIQUETA[f.estado] ?? f.estado}</td>
                      {COLUMNAS.map(([campo]) => (
                        <td key={campo}>{f.crudo[campo] || '—'}</td>
                      ))}
                      <td className="observaciones">
                        {f.errores.map((m) => (
                          <div key={m} className="error">
                            {m}
                          </div>
                        ))}
                        {f.avisos.map((m) => (
                          <div key={m} className="aviso">
                            {m}
                          </div>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {!resultado && (
            <>
              {vista.ya_existen > 0 && (
                <label className="casilla">
                  <input
                    type="checkbox"
                    checked={actualizar}
                    onChange={(e) => setActualizar(e.target.checked)}
                  />
                  Actualizar los {vista.ya_existen} equipos que ya existen con lo que dice la hoja
                </label>
              )}
              {vista.ya_existen > 0 && actualizar && (
                <Mensaje tipo="aviso">
                  Sus fichas se sobrescribirán. Si alguien las corrigió a mano después de la visita,
                  esos cambios se pierden.
                </Mensaje>
              )}

              <div className="acciones">
                <button
                  type="button"
                  onClick={() => void aplicar()}
                  disabled={ocupado || vista.nuevas + (actualizar ? vista.ya_existen : 0) === 0}
                >
                  {ocupado
                    ? 'Importando…'
                    : `Importar ${vista.nuevas + (actualizar ? vista.ya_existen : 0)} equipos`}
                </button>
                <button type="button" className="secundario" onClick={alCerrar}>
                  Cancelar
                </button>
              </div>
            </>
          )}

          {resultado && (
            <div className="acciones">
              <button type="button" onClick={alCerrar}>
                Volver al inventario
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  )
}

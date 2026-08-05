import { useCallback, useEffect, useRef, useState } from 'react'
import { enviar, obtener, subirFichero } from '../api/cliente'
import type { Mapeo, Plantilla } from '../api/tipos'
import { Mensaje, Vacio } from '../ui/Marco'

/** Los campos que el generador sabe rellenar. Debe coincidir con
 *  `CAMPOS_DISPONIBLES` del backend, que es quien lo valida de verdad. */
const CAMPOS = [
  'project.code',
  'project.name',
  'project.client',
  'project.currency',
  'project.asset_count',
  'report.generated_at',
  'capex.total',
  'capex.corto',
  'capex.medio',
  'capex.largo',
  'capex.mejoras',
  'capex.otro',
  'asset.name',
  'asset.city',
  'asset.year_built',
  'asset.total_built_sqm',
]

export function Plantillas() {
  const [plantillas, setPlantillas] = useState<Plantilla[]>([])
  const [elegida, setElegida] = useState<Plantilla | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [subiendo, setSubiendo] = useState(false)
  const entrada = useRef<HTMLInputElement>(null)

  const recargar = useCallback(() => {
    obtener<Plantilla[]>('/report-templates')
      .then(setPlantillas)
      .catch((e: Error) => setError(e.message))
  }, [])

  useEffect(recargar, [recargar])

  async function subir(archivo: File | undefined) {
    if (!archivo) return
    setSubiendo(true)
    setError(null)
    try {
      const nueva = await subirFichero<Plantilla>('/report-templates', archivo, {
        name: archivo.name.replace(/\.pptx$/i, ''),
        language: 'es',
      })
      recargar()
      setElegida(nueva)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se ha podido subir la plantilla')
    } finally {
      setSubiendo(false)
    }
  }

  return (
    <>
      <h1>Plantillas de informe</h1>
      {error && <Mensaje tipo="error">{error}</Mensaje>}

      <div className="filtro">
        <button type="button" onClick={() => entrada.current?.click()} disabled={subiendo}>
          {subiendo ? 'Analizando…' : 'Subir una plantilla PPTX'}
        </button>
        <input
          ref={entrada}
          type="file"
          accept=".pptx"
          hidden
          onChange={(e) => void subir(e.target.files?.[0])}
        />
        <p className="ayuda">
          Se analiza al subirla: si tiene problemas, se descubren ahora y no cuando alguien esté
          esperando un informe.
        </p>
      </div>

      {plantillas.length === 0 ? (
        <Vacio>No hay ninguna plantilla registrada todavía.</Vacio>
      ) : (
        <table className="tabla">
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Idioma</th>
              <th className="numerica">Diapositivas</th>
              <th className="numerica">Marcadores</th>
              <th>Avisos</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {plantillas.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td>{p.language}</td>
                <td className="numerica">{p.slide_count ?? '—'}</td>
                <td className="numerica">{p.analysis?.placeholders.length ?? 0}</td>
                <td>
                  {p.analysis?.has_watermark && (
                    <span className="marca aviso">
                      lleva marca de agua · se retirará al generar
                    </span>
                  )}
                </td>
                <td>
                  <button type="button" className="secundario" onClick={() => setElegida(p)}>
                    Mapear
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {elegida && <EditorDeMapeo plantilla={elegida} alCerrar={() => setElegida(null)} />}
    </>
  )
}

/**
 * Mapeo de marcadores.
 *
 * Cada marcador de la plantilla se ata a un campo, elegido de una lista
 * cerrada. Escribir la expresión a mano permitiría teclear `project.referencia`
 * y descubrir el error al generar, que es el peor momento; la lista lo hace
 * imposible, y el servidor lo vuelve a validar por si acaso.
 */
function EditorDeMapeo({ plantilla, alCerrar }: { plantilla: Plantilla; alCerrar: () => void }) {
  const marcadores = plantilla.analysis?.placeholders ?? []
  const [bindings, setBindings] = useState<Record<string, string>>({})
  const [nombre, setNombre] = useState('Estándar')
  const [guardado, setGuardado] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    obtener<Mapeo[]>(`/report-templates/${plantilla.id}/mappings`)
      .then((lista) => {
        const porDefecto = lista.find((m) => m.is_default) ?? lista[0]
        if (porDefecto) {
          setNombre(porDefecto.name)
          setBindings(porDefecto.bindings)
          return
        }
        // Autoasignación: un marcador que se llama igual que un campo se ata
        // solo. Con veinte marcadores, ahorra veinte desplegables.
        setBindings(
          Object.fromEntries(
            marcadores.filter((m) => CAMPOS.includes(m)).map((m) => [m, m]),
          ),
        )
      })
      .catch(() => setBindings({}))
  }, [plantilla.id, marcadores])

  async function guardar() {
    setError(null)
    try {
      await enviar(`/report-templates/${plantilla.id}/mappings`, {
        name: nombre,
        bindings,
        is_default: true,
      })
      setGuardado(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se ha podido guardar')
    }
  }

  const sinMapear = marcadores.filter((m) => !bindings[m])

  return (
    <div className="dialogo">
      <h3>Mapeo de «{plantilla.name}»</h3>

      <label>
        Nombre del mapeo
        <input value={nombre} onChange={(e) => setNombre(e.target.value)} />
      </label>

      {sinMapear.length > 0 && (
        <Mensaje tipo="aviso">
          {sinMapear.length} marcadores sin origen. Si se genera así, saldrían literalmente en el
          documento: la generación lo impide.
        </Mensaje>
      )}
      {guardado && <Mensaje tipo="ok">Mapeo guardado.</Mensaje>}
      {error && <Mensaje tipo="error">{error}</Mensaje>}

      <table className="tabla compacta">
        <thead>
          <tr>
            <th>Marcador de la plantilla</th>
            <th>Campo del proyecto</th>
          </tr>
        </thead>
        <tbody>
          {marcadores.map((m) => (
            <tr key={m} className={bindings[m] ? '' : 'sin-cambio'}>
              <td>
                <code>{`{{${m}}}`}</code>
              </td>
              <td>
                <select
                  value={bindings[m] ?? ''}
                  onChange={(e) =>
                    setBindings((previos) => {
                      const nuevos = { ...previos }
                      if (e.target.value) nuevos[m] = e.target.value
                      else delete nuevos[m]
                      return nuevos
                    })
                  }
                >
                  <option value="">— sin origen —</option>
                  {CAMPOS.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="acciones">
        <button type="button" onClick={() => void guardar()}>
          Guardar mapeo
        </button>
        <button type="button" className="secundario" onClick={alCerrar}>
          Cerrar
        </button>
      </div>
    </div>
  )
}

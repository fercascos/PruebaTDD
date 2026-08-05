import { useEffect, useState } from 'react'
import { obtener } from '../api/cliente'
import type { Fase } from '../api/tipos'
import { Mensaje, Vacio } from '../ui/Marco'

/**
 * Las fases del proceso.
 *
 * Lo que esta pantalla hace y una lista de estados no haría: enseña **por qué**
 * cada fase está donde está. Dos de ellas —Red Flag/CAPEX y Full Report— tienen
 * el estado derivado del trabajo que hay debajo y no se pueden marcar a mano;
 * aquí se ven etiquetadas como calculadas, para que nadie busque el botón.
 */
export function PestanaFases({ projectId }: { projectId: string }) {
  const [fases, setFases] = useState<Fase[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    obtener<Fase[]>(`/projects/${projectId}/phases`)
      .then(setFases)
      .catch((e: Error) => setError(e.message))
  }, [projectId])

  if (error) return <Mensaje tipo="error">{error}</Mensaje>
  if (!fases) return <p className="cargando">Cargando fases…</p>
  if (fases.length === 0) {
    return (
      <Vacio>
        Este encargo no tiene ninguna fase activa. Las fases se eligen a la carta al darlo de alta.
      </Vacio>
    )
  }

  return (
    <ul className="fases">
      {fases.map((f) => (
        <li key={f.id} className={`fase f-${f.status.toLowerCase()}`}>
          <div className="titulo">
            <strong>{f.name_es}</strong>
            <span className={`estado e-${f.status.toLowerCase()}`}>{f.status}</span>
            {f.es_derivado && (
              <span className="candado" title="Se calcula del trabajo hecho: no se marca a mano">
                calculada
              </span>
            )}
          </div>
          <p className="detalle">{f.detalle}</p>
          {f.estado_sugerido && (
            <p className="sugerencia">
              La aplicación deduce que debería estar en <strong>{f.estado_sugerido}</strong>. Se
              ofrece, no se impone: el responsable puede tener motivos que la aplicación no conoce.
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}

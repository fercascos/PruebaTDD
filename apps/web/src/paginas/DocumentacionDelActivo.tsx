import { useEffect, useState } from 'react'
import { obtener } from '../api/cliente'
import { Mensaje, Vacio } from '../ui/Marco'

/**
 * La documentación **de un activo** `[REQ]` §3.2 b de `docs/23`.
 *
 * ## Esta sección está a medias, y se dice
 *
 * El diseño está cerrado con el cliente —el árbol de su hoja v2: **73 nodos, 60
 * casillas**, verde y gris, cuatro estados por debajo y varios ficheros por
 * casilla— y está transcrito en `docs/05` §5.10, de donde sale la semilla. Lo
 * que no está es construido, y **no se construye hasta que el cliente lo
 * apruebe**: son 3-4 días y es la pieza más cara que queda.
 *
 * Mientras tanto esta sección **no finge**. Enseña los documentos que ya
 * cuelgan de este activo —que existen: `document.asset_id` está desde el primer
 * día— y dice con letras qué va a ocupar su sitio. Una pantalla vacía sin
 * explicación se lee como un fallo; una que promete lo que no hace es peor.
 *
 * `[LIM]` La subida y el checklist siguen viviendo en la pestaña de
 * documentación del proyecto hasta que el árbol la sustituya. Partir esa
 * pantalla en dos ahora significaría hacer dos veces el trabajo: la que quedara
 * se tira entera.
 */

type Documento = {
  id: string
  asset_id: string | null
  display_name: string
  doc_type: string
  confidentiality: string
  version_number: number
  uploaded_at: string
}

/** Los tipos, con el nombre que se lee. Los del enumerado son de la base. */
const TIPOS: Record<string, string> = {
  LICENCIA_URBANISTICA: 'Licencia urbanística',
  PROYECTO: 'Proyecto',
  CONTRATO_MANTENIMIENTO: 'Contrato de mantenimiento',
  LEGALIZACION: 'Legalización',
  CERTIFICADO: 'Certificado',
  GARANTIA: 'Garantía',
  PLANO: 'Plano',
  QA: 'Q&A',
  INFORME_PREVIO: 'Informe previo',
  FICHA_TECNICA: 'Ficha técnica',
  MEMORIA_TECNICA: 'Memoria técnica',
  PLAN_AUTOPROTECCION: 'Plan de autoprotección',
  OTRO: 'Otro',
}

export function DocumentacionDelActivo({
  projectId,
  assetId,
}: {
  projectId: string
  assetId: string
}) {
  const [documentos, setDocumentos] = useState<Documento[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    obtener<Documento[]>(`/projects/${projectId}/documents`)
      .then((todos) => setDocumentos(todos.filter((d) => d.asset_id === assetId)))
      .catch((e: Error) => setError(e.message))
  }, [projectId, assetId])

  return (
    <section className="documentacion-activo">
      {error && <Mensaje tipo="error">{error}</Mensaje>}

      <Mensaje tipo="aviso">
        <strong>Esta sección está por construir.</strong> El árbol acordado —73 nodos y 60
        casillas, verde si hay documentación y gris si no, con cuatro estados por debajo— está
        cerrado y transcrito, pero todavía no se ha construido. Debajo están, mientras tanto,
        los documentos que ya cuelgan de este activo.
      </Mensaje>

      <h3>Documentos de este activo</h3>
      <p className="ayuda">
        Se suben desde «Documentación» del proyecto. Cuando esté el árbol, cada uno caerá en su
        casilla y una casilla podrá tener varios.
      </p>

      {!documentos ? (
        <p className="cargando">Cargando los documentos…</p>
      ) : documentos.length === 0 ? (
        <Vacio>
          Este activo todavía no tiene ningún documento asignado. Que no haya no bloquea nada:
          la due diligence sigue, y lo que falte se declara en las limitaciones del informe.
        </Vacio>
      ) : (
        <div className="desbordable">
          <table className="tabla">
            <thead>
              <tr>
                <th scope="col">Documento</th>
                <th scope="col">Tipo</th>
                <th scope="col">Confidencialidad</th>
                <th scope="col" className="numerica">
                  Versión
                </th>
                <th scope="col">Subido</th>
              </tr>
            </thead>
            <tbody>
              {documentos.map((d) => (
                <tr key={d.id}>
                  <td>{d.display_name}</td>
                  <td>{TIPOS[d.doc_type] ?? d.doc_type}</td>
                  <td>
                    {/* `[REQ]` §15.6 · Un RESTRINGIDO no va a ninguna IA, y quien
                        mira la lista tiene que poder verlo sin abrir la ficha. */}
                    <span
                      className={`pastilla ${d.confidentiality === 'RESTRINGIDO' ? 'aviso' : ''}`}
                    >
                      {d.confidentiality.toLowerCase()}
                    </span>
                  </td>
                  <td className="numerica">v{d.version_number}</td>
                  <td>{d.uploaded_at?.slice(0, 10) ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

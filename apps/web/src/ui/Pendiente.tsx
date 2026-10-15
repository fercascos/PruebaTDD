import type { ReactNode } from 'react'
import { useT } from '../i18n/idioma'

/**
 * El cartel de **funcionalidad pendiente de desarrollar**.
 *
 * `[REQ]` Marcar lo pendiente es una regla del proyecto, no un detalle de esta
 * pantalla: una pantalla que calla y no hace nada se lee como una avería, y la
 * siguiente persona pierde una tarde averiguando si es un fallo o es que no
 * está hecho.
 *
 * No lleva el texto dentro: cada sitio dice **qué** falta y, sobre todo, qué
 * puede hacer quien lo lee mientras tanto. Un cartel que solo dice «pendiente»
 * deja al usuario sin salida.
 */
export function Pendiente({ children }: { children: ReactNode }) {
  const t = useT()
  return (
    <section className="pendiente" role="status">
      <h3>
        <span aria-hidden="true">⚠</span> {t('Pendiente de desarrollar')}
      </h3>
      {children}
    </section>
  )
}

/**
 * La marca corta, para donde no cabe el cartel: una celda de tabla, el rótulo
 * de un botón que no se puede pulsar.
 */
export function MarcaDePendiente() {
  const t = useT()
  return <span className="marca-pendiente">{t('Pendiente de desarrollar')}</span>
}

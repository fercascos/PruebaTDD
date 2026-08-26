import { ErrorDeApi } from '../api/cliente'

/**
 * El texto que se enseña cuando otra persona tocó el registro antes.
 *
 * Un conflicto de versión **no es un error del usuario ni del servidor**: es
 * que hay alguien más trabajando en lo mismo. Tratarlo como un fallo cualquiera
 * —«Error 412»— haría que quien lo recibe volviera a pulsar Guardar, que es
 * justo lo que no hay que hacer: lo que toca es recargar y mirar qué cambió.
 *
 * El mensaje del servidor ya trae el nombre de quien lo modificó, así que se
 * respeta tal cual. Aquí solo se traduce el caso de la cabecera ausente, que es
 * un fallo de la propia aplicación y no algo que el usuario pueda arreglar.
 */
export function mensajeDeConflicto(e: unknown): string {
  if (e instanceof ErrorDeApi && e.status === 428) {
    return (
      'Esta pantalla ha intentado guardar sin decir sobre qué versión escribe. ' +
      'Recargue y vuelva a intentarlo; si se repite, es un fallo de la aplicación.'
    )
  }
  return (e as Error).message
}

/** ¿El fallo viene de que alguien más editó lo mismo? */
export function esConflictoDeVersion(e: unknown): boolean {
  return e instanceof ErrorDeApi && e.esConflictoDeVersion
}

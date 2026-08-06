/**
 * Quita los ceros que sobran a la derecha de la coma.
 *
 * La base guarda los importes como `NUMERIC(18,4)` y la API los devuelve tal
 * cual: «52000.0000», «0.2100». Puestos así en un recuadro editable se leen
 * como un precio con cuatro decimales y un impuesto del 0,21 por mil, y quien
 * corrige un importe acaba dudando de si el número que ve es el que hay.
 *
 * **No redondea**: eso cambiaría el valor. Solo quita ceros que no significan
 * nada, así que «12.3450» queda en «12.345» y no en «12,35». Un precio
 * unitario con cuatro decimales es legítimo —€/m² de una lámina, por ejemplo—
 * y no puede perderlos al pasar por la pantalla.
 */
export function sinCerosSobrantes(valor: string): string {
  if (!valor.includes('.')) return valor
  return valor.replace(/0+$/, '').replace(/\.$/, '')
}

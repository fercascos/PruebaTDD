/**
 * Cola de subida **persistida en IndexedDB** `[REQ]` §15.8.
 *
 * Hasta ahora la cola vivía en memoria: cerrar la pestaña, quedarse sin batería
 * o que el navegador descartara la página en segundo plano —cosa que el móvil
 * hace en cuanto se abre la cámara— perdía las fotos que faltaban por subir.
 * En una visita con casco y sin cobertura eso significa volver a subir al
 * edificio.
 *
 * Lo que se guarda es el **binario entero**, no una referencia. Un `File` de
 * un `<input>` deja de ser legible en cuanto el navegador olvida la página que
 * lo abrió; guardar solo la ruta habría dado una cola llena de elementos que no
 * se pueden subir, que es peor que no tener cola.
 *
 * Se guarda como `ArrayBuffer` con el nombre y el tipo al lado, y el `File` se
 * reconstruye al leer. Guardar el `File` directamente parece más limpio y no lo
 * es: depende de que el navegador sepa serializarlo, y ahí Safari ha tenido
 * fallos con blobs en IndexedDB durante años. En la aplicación que más va a
 * usarse desde un iPhone, esa apuesta no compensa.
 *
 * `[LIM]` Esto es persistencia, **no sincronización en segundo plano**. Las
 * fotos se suben cuando la aplicación está abierta: la Background Sync API no
 * está implementada, y decir lo contrario sería prometer que una visita se sube
 * sola con el móvil en el bolsillo.
 *
 * `[REQ]` Se **pide persistencia** al arrancar, y es lo que separa «la cola
 * aguanta» de «la cola desaparece sola». En Safari de iOS, el almacenamiento de
 * una web que no está en la pantalla de inicio se borra tras **siete días sin
 * abrirla**. Un consultor hace una visita el viernes, no vuelve a abrir la
 * aplicación hasta el lunes de la semana siguiente, y las fotografías que no se
 * subieron ya no están. No es un caso rebuscado: es el calendario normal de un
 * encargo.
 *
 * `[LIM]` Pedirla **no garantiza** que la den. En iOS el permiso llega, en la
 * práctica, cuando la aplicación se añade a la pantalla de inicio. Por eso
 * `persistencia()` devuelve lo que contestó el navegador en vez de tragárselo:
 * quien lo pregunte puede avisar a quien esté delante.
 *
 * `[LIM]` Aun con persistencia concedida, IndexedDB sigue teniendo cuota: si el
 * dispositivo se queda sin espacio, la escritura falla. Eso se ve al guardar,
 * no antes.
 */

import type { ElementoDeCola, EstadoDeElemento, Origen } from './cola'

const BASE = 'tdd-fotos'
const VERSION = 1
const ALMACEN = 'pendientes'

/** Lo que hay en la base: bytes sueltos más lo necesario para rehacer el `File`. */
type Fila = {
  id: string
  projectId: string
  bytes: ArrayBuffer
  nombre: string
  tipo: string
  modificado: number
  origen: Origen
  estado: EstadoDeElemento
  intentos: number
  error?: string
  encolada: number
}

/** Lo que se devuelve, ya con el `File` rehecho. */
export type Guardada = {
  id: string
  projectId: string
  archivo: File
  origen: Origen
  estado: EstadoDeElemento
  intentos: number
  error?: string
  encolada: number
}

function rehacer(fila: Fila): Guardada {
  return {
    id: fila.id,
    projectId: fila.projectId,
    archivo: new File([fila.bytes], fila.nombre, {
      type: fila.tipo,
      lastModified: fila.modificado,
    }),
    origen: fila.origen,
    estado: fila.estado,
    intentos: fila.intentos,
    error: fila.error,
    encolada: fila.encolada,
  }
}

function abrir(): Promise<IDBDatabase> {
  return new Promise((resolver, rechazar) => {
    const peticion = indexedDB.open(BASE, VERSION)
    peticion.onupgradeneeded = () => {
      const db = peticion.result
      if (!db.objectStoreNames.contains(ALMACEN)) {
        const almacen = db.createObjectStore(ALMACEN, { keyPath: 'id' })
        // Por proyecto: al abrir un encargo solo interesa lo suyo, y recorrer
        // toda la cola de todos los encargos para filtrar sería absurdo en un
        // móvil con 400 fotos guardadas.
        almacen.createIndex('projectId', 'projectId')
      }
    }
    peticion.onsuccess = () => resolver(peticion.result)
    peticion.onerror = () => rechazar(peticion.error ?? new Error('No se pudo abrir IndexedDB'))
  })
}

function transaccion<T>(
  modo: IDBTransactionMode,
  hacer: (almacen: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  return abrir().then(
    (db) =>
      new Promise<T>((resolver, rechazar) => {
        const tx = db.transaction(ALMACEN, modo)
        const peticion = hacer(tx.objectStore(ALMACEN))
        // Se resuelve con `oncomplete` y no con `onsuccess`: una escritura que
        // «tuvo éxito» dentro de una transacción que después aborta no está
        // guardada, y prometer lo contrario es justo lo que haría perder fotos.
        tx.oncomplete = () => {
          db.close()
          resolver(peticion.result)
        }
        tx.onerror = tx.onabort = () => {
          db.close()
          rechazar(tx.error ?? new Error('Transacción rechazada'))
        }
      }),
  )
}

/** ¿Hay IndexedDB? En un navegador en modo privado antiguo puede no haberla. */
export function hayAlmacen(): boolean {
  return typeof indexedDB !== 'undefined'
}

/** Qué contestó el navegador cuando se le pidió no borrar esto. */
export type Persistencia = 'concedida' | 'denegada' | 'no-soportada'

/**
 * Pide que el navegador **no** vacíe este almacenamiento por su cuenta.
 *
 * Se pregunta primero con `persisted()`: si ya está concedida, volver a pedirla
 * en cada arranque haría que algunos navegadores enseñaran un diálogo cada vez,
 * y un permiso que se pide sin parar es un permiso que se acaba denegando.
 */
export async function pedirPersistencia(): Promise<Persistencia> {
  const almacenamiento = globalThis.navigator?.storage
  if (!almacenamiento?.persist || !almacenamiento?.persisted) return 'no-soportada'
  try {
    if (await almacenamiento.persisted()) return 'concedida'
    return (await almacenamiento.persist()) ? 'concedida' : 'denegada'
  } catch {
    // Safari ha lanzado aquí en algunas versiones. Que falle pedir permiso no
    // puede impedir usar la cola: sin persistencia sigue funcionando, solo que
    // el navegador puede vaciarla.
    return 'no-soportada'
  }
}

export async function guardar(projectId: string, elemento: ElementoDeCola): Promise<void> {
  if (!hayAlmacen()) return
  // Se leen los bytes ANTES de abrir la transacción: `arrayBuffer()` es
  // asíncrono, y una transacción de IndexedDB se cierra sola en cuanto el
  // hilo queda libre. Leerlos dentro habría dado un «TransactionInactiveError»
  // intermitente, del tipo que solo aparece con ficheros grandes.
  const bytes = await elemento.archivo.arrayBuffer()
  const previa = await transaccion<Fila | undefined>('readonly', (a) => a.get(elemento.id))
  const fila: Fila = {
    id: elemento.id,
    projectId,
    bytes,
    nombre: elemento.archivo.name,
    tipo: elemento.archivo.type,
    modificado: elemento.archivo.lastModified,
    origen: elemento.origen,
    estado: elemento.estado,
    intentos: elemento.intentos,
    error: elemento.error,
    // Al actualizar se conserva el momento original: si se refrescara, cambiar
    // el estado de una foto la mandaría al final de la cola y el orden en que
    // se dispararon las fotos dejaría de significar nada.
    encolada: previa?.encolada ?? Date.now(),
  }
  await transaccion('readwrite', (a) => a.put(fila))
}

export async function guardarVarias(
  projectId: string,
  elementos: readonly ElementoDeCola[],
): Promise<void> {
  for (const elemento of elementos) await guardar(projectId, elemento)
}

/**
 * Quita un elemento de la cola persistida.
 *
 * Se llama cuando la foto **ya está en el servidor**: subida (`HECHO`) o
 * rechazada por duplicada, que también significa que está. Lo fallido se queda:
 * es exactamente lo que hay que poder reintentar mañana.
 */
export async function olvidar(id: string): Promise<void> {
  if (!hayAlmacen()) return
  await transaccion('readwrite', (a) => a.delete(id))
}

export async function pendientesDe(projectId: string): Promise<Guardada[]> {
  if (!hayAlmacen()) return []
  const filas = await transaccion<Fila[]>('readonly', (a) =>
    a.index('projectId').getAll(projectId),
  )
  return [...filas].sort((x, y) => x.encolada - y.encolada).map(rehacer)
}

export async function vaciar(projectId: string): Promise<void> {
  for (const fila of await pendientesDe(projectId)) await olvidar(fila.id)
}

/**
 * Convierte lo guardado en elementos de cola listos para reintentar.
 *
 * `SUBIENDO` vuelve a `PENDIENTE`: si la aplicación se cerró a mitad de una
 * subida, esa foto no está en el servidor y quedarse en «subiendo» para siempre
 * la dejaría en un limbo del que nadie la saca. El contador de intentos se
 * reinicia porque el corte de ayer no dice nada de la cobertura de hoy.
 */
export function comoCola(filas: readonly Guardada[]): ElementoDeCola[] {
  return filas.map((f) => ({
    id: f.id,
    archivo: f.archivo,
    origen: f.origen,
    estado: f.estado === 'SUBIENDO' ? 'PENDIENTE' : f.estado,
    intentos: f.estado === 'SUBIENDO' ? 0 : f.intentos,
    error: f.error,
  }))
}

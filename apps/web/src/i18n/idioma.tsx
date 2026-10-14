/**
 * El idioma de la interfaz `[REQ]` S-05.
 *
 * El supuesto S-05 decía «interfaz en español, con i18n desde el día uno», y
 * avisaba: *«bajo si se prepara ya; alto si se pospone»*. Se pospuso. Esto es
 * la pieza que faltaba, construida cuando el cliente pidió una versión en
 * inglés para sus compañeros.
 *
 * ## Por qué no hay una dependencia
 *
 * `i18next` y `react-intl` resuelven plurales de familias enteras de idiomas,
 * formatos relativos y carga perezosa de paquetes. Aquí hay **dos idiomas con
 * la misma regla de plural** —singular y plural, igual que el inglés— y un
 * paquete de texto que cabe en memoria. Lo que sí hace falta de verdad
 * —importes, fechas y superficies con la convención de cada sitio— lo da
 * `Intl`, que viene en el navegador.
 *
 * La contrapartida está dicha: si algún día entra un idioma con reglas de
 * plural propias —polaco, árabe— esto se queda corto y hay que traer la
 * biblioteca. `[LIM]`
 *
 * ## Por qué la clave es el texto en castellano
 *
 * `t('Proyectos')` y no `t('nav.proyectos')`. Dos razones:
 *
 * 1. **El castellano es el original.** El cliente acaba de reescribirlo entero
 *    (ver `docs/23`), y es el idioma en el que se decide qué dice la pantalla.
 *    Inventar setecientos nombres de clave añadiría una capa que hay que
 *    mantener a mano y en la que un error no se ve.
 * 2. **Una traducción que falta se lee.** Sin entrada en inglés sale el
 *    castellano, que es información —«esto está sin traducir»— y no un
 *    `nav.proyectos` crudo delante de un cliente.
 *
 * `[REQ]` Y para que ese respaldo no se convierta en una excusa, **una prueba
 * falla si queda una sola clave sin traducir**: el hueco es visible en la
 * pantalla y además rompe la construcción.
 *
 * ## Dónde se llama a `traducir()`, y dónde no
 *
 * `[REQ]` La regla, que no es de estilo sino de corrección:
 *
 * > **Se traduce donde se pinta, nunca donde se declara.**
 *
 * Media aplicación tiene tablas de rótulos en constantes de módulo —`const
 * VEREDICTO = { CONFORME: 'Conforme', … }`—. Envolver ahí el valor parece lo
 * cómodo y está mal: el cuerpo de un módulo corre **una vez**, al importarlo,
 * cuando el idioma todavía es el inicial. La tabla se congelaría en castellano
 * y seguiría en castellano después de pulsar «EN», sin que nada falle ni
 * avise. Por eso las constantes guardan el castellano tal cual —que **es** la
 * clave— y quien las lee traduce: `traducir(VEREDICTO[v])`.
 *
 * Y hay un tercer grupo que no se traduce en absoluto: las cadenas que son
 * **dato**, no rótulo. El nombre con el que se da de alta una plantilla
 * («Estándar») viaja al servidor y se guarda; traducirlo crearía plantillas
 * distintas según el idioma de quien las creó.
 */
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react'
import { fijarIdioma, type Idioma, traducir } from './traducir'

// El traductor vive en `./traducir`, sin React, y se reexporta desde aquí para
// que el resto del código lo importe de un solo sitio. El por qué, allí.
export type { Idioma } from './traducir'
export { traducir } from './traducir'

/** Lo que `Intl` necesita para cada idioma. La moneda la fija el proyecto. */
const LOCALE: Record<Idioma, string> = { es: 'es-ES', en: 'en-GB' }

const CLAVE_GUARDADA = 'tdd.idioma'

/**
 * El idioma inicial: lo que el usuario eligiera la última vez, y si no, lo que
 * pida el navegador. Castellano por omisión, que es el idioma del producto.
 */
function idiomaInicial(): Idioma {
  try {
    const guardado = localStorage.getItem(CLAVE_GUARDADA)
    if (guardado === 'es' || guardado === 'en') return guardado
  } catch {
    // Navegación privada o almacenamiento bloqueado: no es un error, se sigue
    // con el idioma del navegador.
  }
  return navigator.language?.toLowerCase().startsWith('en') ? 'en' : 'es'
}

type Contexto = {
  idioma: Idioma
  cambiar: (a: Idioma) => void
}

const Ctx = createContext<Contexto>({ idioma: 'es', cambiar: () => {} })

export function ProveedorDeIdioma({ children }: { children: ReactNode }) {
  const [idioma, setIdioma] = useState<Idioma>(() => {
    const inicial = idiomaInicial()
    fijarIdioma(inicial)
    return inicial
  })

  const cambiar = useCallback((a: Idioma) => {
    // El orden importa: primero el valor que lee `traducir()`, después el
    // estado que provoca el repintado. Al revés, la primera pasada del
    // repintado leería todavía el idioma viejo.
    fijarIdioma(a)
    setIdioma(a)
    try {
      localStorage.setItem(CLAVE_GUARDADA, a)
    } catch {
      // Igual que arriba: se cambia el idioma aunque no se pueda recordar.
    }
    document.documentElement.lang = a
  }, [])

  const valor = useMemo(() => ({ idioma, cambiar }), [idioma, cambiar])
  return <Ctx.Provider value={valor}>{children}</Ctx.Provider>
}

export function useIdioma(): Contexto {
  return useContext(Ctx)
}

/**
 * Traduce, suscribiendo el componente al idioma.
 *
 * Es `traducir()` más el repintado: dentro de un componente se usa esto, y
 * fuera —constantes, ayudantes, un `catch`— la función suelta.
 */
export function useT(): (clave: string, valores?: Record<string, string | number>) => string {
  // Se suscribe al contexto —para que el componente se repinte al cambiar de
  // idioma— y delega en la misma función que usa todo lo demás, para que no
  // haya dos traductores que puedan discrepar.
  useIdioma()
  return traducir
}

/**
 * Importes, números y fechas con la convención del idioma.
 *
 * `[REQ]` Sin esto la traducción se queda a medias y se nota: `'es-ES'` estaba
 * escrito a mano en seis sitios del frontend, así que una pantalla en inglés
 * seguiría enseñando «1.099.100,00 €» —punto de millares, coma decimal— a
 * alguien que espera «€1,099,100.00».
 */
export function useFormato() {
  const { idioma } = useIdioma()
  return useMemo(() => {
    const l = LOCALE[idioma]
    const euros = new Intl.NumberFormat(l, {
      style: 'currency',
      currency: 'EUR',
      maximumFractionDigits: 0,
    })
    const eurosExactos = new Intl.NumberFormat(l, {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
    const numero = new Intl.NumberFormat(l)
    const fecha = new Intl.DateTimeFormat(l, { dateStyle: 'medium' })
    const fechaYHora = new Intl.DateTimeFormat(l, { dateStyle: 'medium', timeStyle: 'short' })
    return {
      locale: l,
      euros: (n: number) => euros.format(n),
      eurosExactos: (n: number) => eurosExactos.format(n),
      numero: (n: number) => numero.format(n),
      superficie: (n: number) => `${numero.format(n)} m²`,
      fecha: (iso: string) => fecha.format(new Date(iso)),
      fechaYHora: (iso: string) => fechaYHora.format(new Date(iso)),
    }
  }, [idioma])
}

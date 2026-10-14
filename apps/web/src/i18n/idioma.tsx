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
 */
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react'
import { EN } from './textos'

export type Idioma = 'es' | 'en'

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
  const [idioma, setIdioma] = useState<Idioma>(idiomaInicial)

  const cambiar = useCallback((a: Idioma) => {
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
 * Traduce. En castellano devuelve la clave tal cual, que **es** el texto.
 *
 * `interpolacion` sustituye `{nombre}` por su valor. Se resuelve después de
 * traducir, para que la frase inglesa pueda colocar los huecos en otro orden.
 */
export function useT(): (clave: string, valores?: Record<string, string | number>) => string {
  const { idioma } = useIdioma()
  return useCallback(
    (clave: string, valores?: Record<string, string | number>) => {
      const texto = idioma === 'en' ? (EN[clave] ?? clave) : clave
      if (!valores) return texto
      return texto.replace(/\{(\w+)\}/g, (entero, nombre) =>
        nombre in valores ? String(valores[nombre]) : entero,
      )
    },
    [idioma],
  )
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

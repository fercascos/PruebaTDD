import { useEffect, useState } from 'react'
import { peticionAutenticada } from '../api/cliente'

/**
 * Una imagen de la API, **con la credencial puesta**.
 *
 * Un `<img src="/api/v1/photos/…/download">` a secas no funciona aquí: el
 * token de acceso vive en memoria y no en una cookie —a propósito, para que no
 * lo lea ningún script— y el navegador no le pone ninguna cabecera a la
 * petición que dispara un `src`. El resultado era un `401` por cada foto y una
 * rejilla entera de recuadros rotos.
 *
 * Así que se descarga con `fetch`, que sí lleva la cabecera, y se pinta desde
 * un `blob:`. El `URL.revokeObjectURL` del cierre no es cosmético: sin él, cada
 * vuelta por la pestaña de fotos deja los binarios retenidos en memoria hasta
 * que se recarga la página.
 *
 * `[LIM]` Cada montaje descarga de nuevo. Con `MINIATURA_320` el coste es
 * pequeño, pero una caché por identificador sigue pendiente.
 *
 * **Con almacén S3 la API responde un `302` a una URL firmada**, y `fetch` lo
 * sigue solo. Dos cosas de las que depende eso, y que no se ven desde aquí:
 *
 * 1. El navegador **quita la cabecera `Authorization`** al seguir una
 *    redirección a otro origen, que es justo lo que hace falta: el permiso
 *    viaja ya en la firma de la URL.
 * 2. El bucket **tiene que permitir el origen de la aplicación en CORS**. Sin
 *    eso, S3 devuelve el objeto y el navegador se niega a entregarlo al
 *    JavaScript: la rejilla sale vacía y **no aparece ningún error en el log
 *    del servidor**. `AlmacenS3.comprobar()` lo avisa al arrancar.
 *
 * `[LIM]` Ese camino no se ha probado en un navegador contra un S3 real: en el
 * entorno de desarrollo el almacén es el de disco y devuelve el binario.
 */
export function Imagen({
  ruta,
  alt,
  className,
}: {
  ruta: string
  alt: string
  className?: string
}) {
  const [url, setUrl] = useState<string | null>(null)
  const [fallo, setFallo] = useState(false)

  useEffect(() => {
    let vigente = true
    let creada: string | null = null
    const abortador = new AbortController()

    peticionAutenticada(ruta, abortador.signal)
      .then((blob) => {
        if (!vigente) return
        creada = URL.createObjectURL(blob)
        setUrl(creada)
      })
      .catch(() => {
        if (vigente) setFallo(true)
      })

    return () => {
      vigente = false
      abortador.abort()
      if (creada) URL.revokeObjectURL(creada)
    }
  }, [ruta])

  if (fallo) {
    // Un hueco con explicación, no un icono roto: el usuario tiene que poder
    // distinguir «no se ha podido cargar» de «esta foto está vacía».
    return <span className="imagen-fallida">no se ha podido cargar</span>
  }
  if (!url) return <span className="imagen-cargando" aria-busy="true" />
  return <img src={url} alt={alt} className={className} />
}

import { useCallback, useEffect, useState } from 'react'
import { ErrorDeApi, enviar, obtener } from '../api/cliente'
import type { Perfil } from '../api/tipos'
import { Campo, Formulario } from '../ui/Formulario'
import { Mensaje, Vacio } from '../ui/Marco'

type Sugerencia = {
  id: string
  type: string
  status: string
  title: string
  body: string
  created_at: string
  resolution_note: string | null
}

/**
 * Los cuatro tipos que admite `suggestion_type`. **Ni uno más**: el desplegable
 * llegó a ofrecer «Texto reutilizable» y «Otro», que no existen en el
 * enumerado, y elegirlos devolvía un 422 sin que nada en la pantalla avisara.
 * Un desplegable con opciones que el servidor rechaza es peor que uno corto.
 */
const TIPOS = [
  { code: 'PRECIO', nombre: 'Precio de referencia' },
  { code: 'CATALOGO', nombre: 'Catálogo (código, zona, concepto)' },
  { code: 'PLANTILLA', nombre: 'Plantilla de informe' },
  { code: 'APLICACION', nombre: 'La propia aplicación' },
] as const

/** Lo que puede hacer quien atiende el buzón. `[REQ]` P-41. */
const RESOLUCIONES = {
  EN_REVISION: { etiqueta: 'Pasar a revisión', exigeNota: false },
  ACEPTADA: { etiqueta: 'Aceptar', exigeNota: false },
  RECHAZADA: { etiqueta: 'Rechazar', exigeNota: true },
  DUPLICADA: { etiqueta: 'Marcar duplicada', exigeNota: false },
  APLICADA: { etiqueta: 'Marcar aplicada', exigeNota: false },
} as const

/**
 * Las mismas transiciones que la máquina de estados del servidor.
 *
 * Se replican aquí para **no ofrecer botones que van a fallar**: la pantalla
 * mostraba «Aceptar» sobre una propuesta recién llegada, y pulsarlo devolvía un
 * 409 porque desde `NUEVA` solo se puede pasar a revisión o marcar duplicada.
 * La regla sigue viviendo en el servidor —esto no la relaja, solo evita
 * enseñar caminos cerrados—; si las dos listas divergen, el 409 sigue ahí.
 */
const SIGUIENTES: Record<string, readonly (keyof typeof RESOLUCIONES)[]> = {
  NUEVA: ['EN_REVISION', 'DUPLICADA'],
  EN_REVISION: ['ACEPTADA', 'RECHAZADA', 'DUPLICADA'],
  ACEPTADA: ['APLICADA'],
  RECHAZADA: [],
  DUPLICADA: [],
  APLICADA: [],
}

/**
 * Módulo de Sugerencias `[REQ]`.
 *
 * > *«un módulo extra que sea "Sugerencias" y que sirva para que cada usuario
 * > el día de mañana proponga cambios y solo el/los usuario/s administrador
 * > pueda/n ver las propuestas»* — y P-40: *«haz que sí, que vea las suyas»*.
 *
 * La visibilidad **no se decide en esta pantalla**: la impone la Row Level
 * Security sobre la tabla. Si mañana alguien escribe una consulta nueva y
 * olvida filtrar por autor, la fila sigue sin aparecer. Aquí solo se elige qué
 * listado pedir.
 */
export function Sugerencias() {
  const [perfil, setPerfil] = useState<Perfil | null>(null)
  const [mias, setMias] = useState<Sugerencia[]>([])
  const [bandeja, setBandeja] = useState<Sugerencia[] | null>(null)
  const [proponiendo, setProponiendo] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // El permiso efectivo lo calcula el servidor y viaja en el perfil: deducirlo
  // aquí otra vez sería el tercer sitio donde la misma regla puede desviarse.
  const gestiona = perfil?.gestiona_sugerencias ?? false

  const recargar = useCallback(() => {
    obtener<Sugerencia[]>('/suggestions/mine')
      .then(setMias)
      .catch((e: Error) => setError(e.message))
    // La bandeja completa solo se pide si el perfil la puede ver: pedirla
    // siempre produciría un 403 en el registro cada vez que entra un consultor.
    obtener<Perfil>('/auth/me')
      .then((p) => {
        setPerfil(p)
        if (p.gestiona_sugerencias) {
          obtener<Sugerencia[]>('/suggestions')
            .then(setBandeja)
            .catch(() => setBandeja([]))
        }
      })
      .catch(() => setPerfil(null))
  }, [])

  useEffect(recargar, [recargar])

  return (
    <>
      <h1>Sugerencias</h1>
      <p className="ayuda">
        Proponga cambios en precios, catálogos, textos o plantillas. Las propuestas las atiende un
        administrador; usted ve siempre las suyas.
      </p>
      {error && <Mensaje tipo="error">{error}</Mensaje>}

      {proponiendo ? (
        <NuevaSugerencia
          alGuardar={() => {
            setProponiendo(false)
            recargar()
          }}
          alCancelar={() => setProponiendo(false)}
        />
      ) : (
        <button type="button" onClick={() => setProponiendo(true)}>
          Proponer un cambio
        </button>
      )}

      <h3>Mis propuestas</h3>
      {mias.length === 0 ? (
        <Vacio>Todavía no ha propuesto ningún cambio.</Vacio>
      ) : (
        <Lista sugerencias={mias} />
      )}

      {gestiona && (
        <>
          <h3>Bandeja de propuestas</h3>
          <p className="ayuda">
            Todas las de la organización. Este listado solo lo ve quien atiende el buzón, y no
            porque esta pantalla lo esconda: la base de datos no devuelve las filas.
          </p>
          {bandeja === null ? (
            <p className="cargando">Cargando la bandeja…</p>
          ) : bandeja.length === 0 ? (
            <Vacio>No hay propuestas pendientes.</Vacio>
          ) : (
            <Lista sugerencias={bandeja} conAcciones alCambiar={recargar} />
          )}
        </>
      )}
    </>
  )
}

function Lista({
  sugerencias,
  conAcciones = false,
  alCambiar,
}: {
  sugerencias: Sugerencia[]
  conAcciones?: boolean
  alCambiar?: () => void
}) {
  return (
    <ul className="sugerencias">
      {sugerencias.map((s) => (
        <li key={s.id}>
          <div className="titulo">
            <strong>{s.title}</strong>
            <span className={`estado e-${s.status.toLowerCase()}`}>{s.status}</span>
            <span className="marca">{s.type}</span>
          </div>
          <p className="detalle">{s.body}</p>
          {s.resolution_note && <p className="sugerencia">Respuesta: {s.resolution_note}</p>}
          {conAcciones && alCambiar && <Acciones sugerencia={s} alCambiar={alCambiar} />}
        </li>
      ))}
    </ul>
  )
}

function Acciones({ sugerencia, alCambiar }: { sugerencia: Sugerencia; alCambiar: () => void }) {
  const [nota, setNota] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function resolver(destino: string, exigeNota: boolean) {
    setError(null)
    if (exigeNota && !nota.trim()) {
      // El servidor lo exige igualmente con un 422; decirlo aquí ahorra el
      // viaje y deja claro qué falta.
      setError('Rechazar una propuesta exige explicar por qué: lo lee quien la escribió')
      return
    }
    try {
      await enviar(`/suggestions/${sugerencia.id}/transitions`, {
        to: destino,
        resolution_note: nota.trim() || null,
      })
      alCambiar()
    } catch (e) {
      setError(e instanceof ErrorDeApi ? e.message : 'No se ha podido resolver')
    }
  }

  const destinos = SIGUIENTES[sugerencia.status] ?? []
  if (destinos.length === 0) return null

  return (
    <div className="acciones-sugerencia">
      <input
        placeholder="Nota de respuesta (obligatoria al rechazar)"
        value={nota}
        onChange={(e) => setNota(e.target.value)}
      />
      {destinos.map((destino) => (
        <button
          key={destino}
          type="button"
          className="secundario"
          onClick={() => void resolver(destino, RESOLUCIONES[destino].exigeNota)}
        >
          {RESOLUCIONES[destino].etiqueta}
        </button>
      ))}
      {error && <Mensaje tipo="error">{error}</Mensaje>}
    </div>
  )
}

function NuevaSugerencia({
  alGuardar,
  alCancelar,
}: {
  alGuardar: () => void
  alCancelar: () => void
}) {
  const [tipo, setTipo] = useState<string>('PRECIO')
  const [titulo, setTitulo] = useState('')
  const [cuerpo, setCuerpo] = useState('')

  return (
    <Formulario
      titulo="Proponer un cambio"
      textoDeEnvio="Enviar propuesta"
      alCancelar={alCancelar}
      enviar={async () => {
        // Nótese lo que NO se envía: ni la organización ni el autor. Se toman
        // del token, nunca del cuerpo, y la RLS impide escribir a nombre ajeno.
        await enviar('/suggestions', {
          type: tipo,
          title: titulo.trim(),
          body: cuerpo.trim(),
        })
        alGuardar()
      }}
    >
      <Campo etiqueta="Tipo">
        <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
          {TIPOS.map((t) => (
            <option key={t.code} value={t.code}>
              {t.nombre}
            </option>
          ))}
        </select>
      </Campo>
      <Campo etiqueta="Título">
        <input
          required
          maxLength={160}
          value={titulo}
          onChange={(e) => setTitulo(e.target.value)}
          placeholder="El precio de la impermeabilización está desfasado"
        />
      </Campo>
      <Campo etiqueta="Explicación">
        <textarea
          required
          rows={4}
          value={cuerpo}
          onChange={(e) => setCuerpo(e.target.value)}
          placeholder="Qué cambiaría y por qué"
        />
      </Campo>
    </Formulario>
  )
}

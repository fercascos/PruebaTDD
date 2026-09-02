import { useEffect, useState } from 'react'
import { enviar, obtener } from '../api/cliente'
import type { Activo, ElementoCatalogo } from '../api/tipos'
import { Campo, Formulario, Rejilla } from '../ui/Formulario'

/**
 * Alta y edición de un activo.
 *
 * `[REQ]` P-02 · La ficha es la **unión** de §3.1.3 y §3.3.1. Los campos que no
 * aplican a una tipología **no se ocultan destruyendo el dato**: se agrupan
 * aparte y se marcan. Con una ficha por tipología, cambiar de nave a oficinas y
 * volver atrás habría perdido la altura de almacén; aquí sigue ahí, y el
 * backend lo garantiza con una prueba.
 */

/** Campos que solo tienen sentido en industrial/logístico. `[REC]` §3.3.1. */
const CAMPOS_DE_ALMACEN = ['warehouse_area_sqm', 'office_area_sqm', 'warehouse_height_m'] as const

type Numericos = Record<string, string>

export function FichaDeActivo({
  projectId,
  activo,
  alGuardar,
  alCancelar,
}: {
  projectId: string
  activo?: Activo
  alGuardar: () => void
  alCancelar: () => void
}) {
  const [tipologias, setTipologias] = useState<ElementoCatalogo[]>([])
  const [tipologia, setTipologia] = useState(activo?.typology_id ?? '')
  const [nombre, setNombre] = useState(activo?.name ?? '')
  const [codigo, setCodigo] = useState(activo?.asset_code ?? '')
  const [ciudad, setCiudad] = useState(activo?.city ?? '')
  const [ano, setAno] = useState(activo?.year_built?.toString() ?? '')
  const [reforma, setReforma] = useState(activo?.year_last_refurb?.toString() ?? '')
  // Todos los campos se cargan del activo. Cinco de los seis arrancaban en
  // cadena vacía y solo `total_built_sqm` se leía, así que al abrir una ficha
  // ya rellena se veían huecos donde había datos. Y con `year_last_refurb` era
  // **pérdida de datos**: `guardar()` manda `null` cuando está vacío sin
  // condición, así que abrir un activo con año de reforma y pulsar Guardar lo
  // borraba en silencio.
  const [numericos, setNumericos] = useState<Numericos>({
    plot_area_sqm: activo?.plot_area_sqm ?? '',
    total_built_sqm: activo?.total_built_sqm ?? '',
    lettable_area_sqm: activo?.lettable_area_sqm ?? '',
    warehouse_area_sqm: activo?.warehouse_area_sqm ?? '',
    office_area_sqm: activo?.office_area_sqm ?? '',
    warehouse_height_m: activo?.warehouse_height_m ?? '',
    // `[REQ]` Lo que aporta la memoria técnica. Van con los demás porque se
    // guardan igual; lo que cambia es de dónde salen.
    footprint_area_sqm: activo?.footprint_area_sqm ?? '',
    urbanised_area_sqm: activo?.urbanised_area_sqm ?? '',
    usable_area_sqm: activo?.usable_area_sqm ?? '',
    max_height_m: activo?.max_height_m ?? '',
  })
  const [catastro, setCatastro] = useState(activo?.cadastral_reference ?? '')
  const [promotor, setPromotor] = useState(activo?.developer ?? '')
  const [fechaProyecto, setFechaProyecto] = useState(activo?.project_date ?? '')
  const [usoSecundario, setUsoSecundario] = useState(activo?.secondary_use ?? '')
  const [muelles, setMuelles] = useState(activo?.loading_docks?.toString() ?? '')
  const [plazas, setPlazas] = useState(activo?.parking_spaces?.toString() ?? '')

  useEffect(() => {
    obtener<ElementoCatalogo[]>('/catalogs/asset-typologies')
      .then((lista) => {
        setTipologias(lista)
        if (!activo && lista[0]) setTipologia(lista[0].id)
      })
      .catch(() => setTipologias([]))
  }, [activo])

  const esIndustrial =
    tipologias.find((t) => t.id === tipologia)?.code?.toUpperCase().includes('INDUSTRIAL') ?? false

  function numero(clave: string) {
    return {
      value: numericos[clave] ?? '',
      onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
        setNumericos((previos) => ({ ...previos, [clave]: e.target.value })),
    }
  }

  async function guardar() {
    // Solo se mandan los campos con valor: enviar cadenas vacías convertiría un
    // «no lo sé» en un cero, y un cero en una superficie es una afirmación.
    const cuerpo: Record<string, unknown> = {
      name: nombre.trim(),
      typology_id: tipologia,
      asset_code: codigo.trim() || null,
      city: ciudad.trim() || null,
      year_built: ano ? Number(ano) : null,
      year_last_refurb: reforma ? Number(reforma) : null,
      cadastral_reference: catastro.trim() || null,
      developer: promotor.trim() || null,
      project_date: fechaProyecto || null,
      secondary_use: usoSecundario.trim() || null,
      loading_docks: muelles ? Number(muelles) : null,
      parking_spaces: plazas ? Number(plazas) : null,
    }
    for (const [clave, valor] of Object.entries(numericos)) {
      if (valor.trim()) cuerpo[clave] = valor.trim()
    }
    if (activo) await enviar(`/assets/${activo.id}`, cuerpo, 'PATCH')
    else await enviar(`/projects/${projectId}/assets`, cuerpo)
    alGuardar()
  }

  return (
    <Formulario
      titulo={activo ? `Editar «${activo.name}»` : 'Nuevo activo'}
      enviar={guardar}
      textoDeEnvio={activo ? 'Guardar cambios' : 'Crear activo'}
      alCancelar={alCancelar}
    >
      <Rejilla>
        <Campo etiqueta="Nombre">
          <input required maxLength={200} value={nombre} onChange={(e) => setNombre(e.target.value)} />
        </Campo>
        <Campo etiqueta="Código del cliente">
          <input maxLength={60} value={codigo} onChange={(e) => setCodigo(e.target.value)} />
        </Campo>
        <Campo etiqueta="Tipología" ayuda="Determina las zonas disponibles al registrar hallazgos">
          <select required value={tipologia} onChange={(e) => setTipologia(e.target.value)}>
            {tipologias.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name_es}
              </option>
            ))}
          </select>
        </Campo>
        <Campo etiqueta="Ciudad">
          <input maxLength={120} value={ciudad} onChange={(e) => setCiudad(e.target.value)} />
        </Campo>
        <Campo etiqueta="Año de construcción">
          <input
            type="number"
            min={1500}
            max={2100}
            value={ano}
            onChange={(e) => setAno(e.target.value)}
          />
        </Campo>
        <Campo etiqueta="Año de última reforma" ayuda="No puede ser anterior al de construcción">
          <input
            type="number"
            min={1500}
            max={2100}
            value={reforma}
            onChange={(e) => setReforma(e.target.value)}
          />
        </Campo>
        <Campo etiqueta="Superficie de parcela (m²)">
          <input type="number" step="0.01" min={0} {...numero('plot_area_sqm')} />
        </Campo>
        <Campo etiqueta="Superficie construida total (m²)">
          <input type="number" step="0.01" min={0} {...numero('total_built_sqm')} />
        </Campo>
        <Campo etiqueta="Superficie alquilable (m²)">
          <input type="number" step="0.01" min={0} {...numero('lettable_area_sqm')} />
        </Campo>
      </Rejilla>

      <h3>
        Datos de nave{' '}
        {!esIndustrial && (
          <span className="candado">
            no aplican a esta tipología · lo que escriba se conserva igualmente
          </span>
        )}
      </h3>
      <p className="ayuda">
        `[REQ]` P-02 · Estos campos se guardan siempre. Reclasificar el activo no los borra: si
        mañana vuelve a ser una nave, la altura de almacén sigue ahí.
      </p>
      <Rejilla>
        {CAMPOS_DE_ALMACEN.map((clave) => (
          <Campo
            key={clave}
            etiqueta={
              clave === 'warehouse_area_sqm'
                ? 'Superficie de almacén (m²)'
                : clave === 'office_area_sqm'
                  ? 'Superficie de oficinas (m²)'
                  : 'Altura libre de almacén (m)'
            }
          >
            <input type="number" step="0.01" min={0} {...numero(clave)} />
          </Campo>
        ))}
      </Rejilla>

      {/* `[REQ]` Lo que aporta la memoria técnica del edificio. Va en su propio
          bloque porque tiene otro origen: los de arriba los teclea quien da de
          alta el encargo, éstos salen del documento que entrega la propiedad. */}
      <h3>
        Datos de la memoria técnica{' '}
        {activo?.memoria_validada_at ? (
          <span className="candado">validada</span>
        ) : (
          <span className="candado">sin validar</span>
        )}
      </h3>
      <p className="ayuda">
        Salen de la memoria técnica del edificio. Mientras ponga «sin validar», nadie ha revisado
        que sean correctos: un dato leído de un documento no es lo mismo que uno tecleado por un
        técnico.
      </p>
      <Rejilla>
        <Campo etiqueta="Referencia catastral">
          <input value={catastro} maxLength={30} onChange={(e) => setCatastro(e.target.value)} />
        </Campo>
        <Campo etiqueta="Promotor">
          <input value={promotor} maxLength={200} onChange={(e) => setPromotor(e.target.value)} />
        </Campo>
        <Campo etiqueta="Fecha del proyecto">
          <input
            type="date"
            value={fechaProyecto}
            onChange={(e) => setFechaProyecto(e.target.value)}
          />
        </Campo>
        <Campo etiqueta="Uso secundario">
          <input
            value={usoSecundario}
            maxLength={120}
            onChange={(e) => setUsoSecundario(e.target.value)}
          />
        </Campo>
        {/* Los tres que se confunden con los de arriba. La etiqueta lo dice
            entera: «huella», «útil» y «del edificio» son lo que los distingue
            de la construida, la alquilable y la del almacén. */}
        <Campo etiqueta="Superficie ocupada por el edificio · huella (m²)">
          <input type="number" step="0.01" min={0} {...numero('footprint_area_sqm')} />
        </Campo>
        <Campo etiqueta="Superficie urbanizada (m²)">
          <input type="number" step="0.01" min={0} {...numero('urbanised_area_sqm')} />
        </Campo>
        <Campo etiqueta="Superficie útil total (m²)">
          <input type="number" step="0.01" min={0} {...numero('usable_area_sqm')} />
        </Campo>
        <Campo etiqueta="Altura máxima del edificio (m)">
          <input type="number" step="0.01" min={0} {...numero('max_height_m')} />
        </Campo>
        <Campo etiqueta="Muelles de carga">
          <input
            type="number"
            min={0}
            value={muelles}
            onChange={(e) => setMuelles(e.target.value)}
          />
        </Campo>
        <Campo etiqueta="Plazas de aparcamiento">
          <input type="number" min={0} value={plazas} onChange={(e) => setPlazas(e.target.value)} />
        </Campo>
      </Rejilla>
    </Formulario>
  )
}

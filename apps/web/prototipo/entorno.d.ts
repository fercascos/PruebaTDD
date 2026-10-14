/** Lo que la compilación del prototipo inyecta y declara. */

/** El idioma con el que se compiló, de `TDD_IDIOMA`. Ver `vite.prototipo.config.ts`. */
declare const __TDD_IDIOMA__: 'es' | 'en'

/**
 * La grabación de la API, incrustada.
 *
 * Especificador desnudo y no una ruta: lo resuelve un alias de Vite, que es lo
 * que permite elegir `grabacion.json` o `grabacion-en.json` al compilar sin
 * renombrar nada.
 */
declare module 'grabacion' {
  const grabacion: unknown
  export default grabacion
}

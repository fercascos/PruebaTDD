import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// El puerto 5174 y el 8001 son los del ESG: el proyecto de due diligence usa
// el 5173 y el 8000, y los dos se levantan a la vez en la misma máquina.
// `loadEnv` y no `process.env`: el fichero de configuración se comprueba con
// el mismo `tsconfig` que la aplicación, que no lleva los tipos de Node.
export default defineConfig(({ mode }) => {
  const entorno = loadEnv(mode, process.cwd(), 'ESG_')
  return {
    plugins: [react()],
    server: {
      port: 5174,
      proxy: {
        '/api': { target: entorno.ESG_API ?? 'http://localhost:8001', changeOrigin: true },
      },
    },
  }
})

# Entregables

Lo que se le entrega a alguien que no va a montar nada: el **prototipo
navegable**, un fichero HTML por idioma que se abre con doble clic, sin
servidor, sin base de datos y sin red.

| Fichero | |
|---|---|
| `TDD-prototipo-ES.html` | Castellano |
| `TDD-prototype-EN.html` | Inglés |

`[REQ]` No son maquetas. Cada uno es `apps/web/src/App.tsx` —las mismas
pantallas, el mismo cliente HTTP, la misma hoja de estilos— con dos cambios y
ninguno más: sus peticiones las contesta una **grabación de la API real** sobre
un encargo de demostración con datos ficticios, y las rutas van en el fragmento
(`#/proyectos`) porque un fichero suelto no tiene detrás quien sirva
`/proyectos` al recargar.

Se navega y se filtra. **No se guarda nada**, y lo dice un aviso en la cabecera.

## Están generados, así que envejecen

Salen de compilar la aplicación, y **nada avisa cuando se quedan viejos**. Ya
pasó una vez: la grabación inglesa era de unas horas antes de traducir las
frases de la API, y el fichero enseñaba pantallas inglesas con castellano
dentro.

Para refrescarlos, con la API y la base de demostración en marcha:

```bash
cd apps/web

TDD_PROYECTO=<uuid> npm run prototipo:grabar
npm run prototipo

TDD_PROYECTO=<uuid> TDD_IDIOMA=en TDD_GRABACION=prototipo/grabacion-en.json npm run prototipo:grabar
TDD_IDIOMA=en npm run prototipo

node herramientas/comprobar-prototipo.mjs      # 19 pantallas, ningún castellano
TDD_IDIOMA=es node herramientas/comprobar-prototipo.mjs   # control: las 19 encendidas

cp prototipo/entregable/prototipo.html    ../../entregables/TDD-prototipo-ES.html
cp prototipo/entregable/prototipo-en.html ../../entregables/TDD-prototype-EN.html
```

`[REQ]` El grabador se apunta **solo a una base de demostración con datos
ficticios**. Lo que grabe acaba dentro de un fichero que se comparte; con datos
de un cliente sería publicar su proyecto.

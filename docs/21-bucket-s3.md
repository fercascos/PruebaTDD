# El bucket de S3, y los permisos exactos

`[REQ]` §13 · Guía para crear el bucket de producción y la política del rol de la aplicación.
No es documentación de cortesía: **la mitad de estas cosas no se pueden cambiar después**, y la otra
mitad falla de una forma que no se ve desde el servidor.

Todo lo de aquí está **sin ejecutar contra AWS**. El adaptador se ha probado contra `moto` y contra
un MinIO real; ninguno de los dos es AWS. Lo que sigue sale de leer el código y la documentación de
S3, y hay que recorrerlo una vez con `tools/comprobar_almacen.py` antes de dar por bueno el bucket.

---

## 1. Crear el bucket

```bash
REGION=eu-west-1
CUBO=tdd-evidencia-prod

# Object Lock se activa AL CREAR el bucket. Activarlo sobre uno que ya existe
# tiene requisitos aparte y [PDV] no se ha verificado aquí: dé por hecho que si
# el bucket se creó sin él, hay que crear otro y copiar.
aws s3api create-bucket \
  --bucket "$CUBO" --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION" \
  --object-lock-enabled-for-bucket

# El versionado lo activa `--object-lock-enabled-for-bucket`, pero se afirma
# aquí porque es lo que sostiene que sobrescribir una clave no destruya bytes.
aws s3api put-bucket-versioning \
  --bucket "$CUBO" --versioning-configuration Status=Enabled

# Nada público. La aplicación sirve por URL firmada, que caduca a los 5 minutos.
aws s3api put-public-access-block --bucket "$CUBO" \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

# Cifrado en reposo. AWS cifra por defecto desde 2023; se pone explícito para
# que se vea, y para que un cambio futuro del valor por defecto no lo apague.
aws s3api put-bucket-encryption --bucket "$CUBO" \
  --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"},"BucketKeyEnabled":true}]}'
```

### Y las reglas CORS, que no son opcionales

Sin ellas la aplicación falla **de la peor manera posible**: la API redirige bien, S3 devuelve el
objeto, y el navegador se niega a entregárselo al JavaScript por falta de
`Access-Control-Allow-Origin`. La rejilla de fotografías sale vacía y **en el servidor no aparece ni
un error**. MinIO acepta cualquier origen por defecto, así que esto **no se nota en desarrollo**.

```bash
aws s3api put-bucket-cors --bucket "$CUBO" --cors-configuration '{
  "CORSRules": [{
    "AllowedOrigins": ["https://tdd.sudominio.example"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["Content-Length", "Content-Type"],
    "MaxAgeSeconds": 300
  }]
}'
```

`[REQ]` El origen es el de **la aplicación**, no el del bucket, y va con `https://` y sin barra
final. Un `*` aquí no es una simplificación: es dejar que cualquier página lea las fotografías de un
cliente si consigue una URL firmada.

---

## 2. La política del rol de la aplicación

`[REQ]` Mínimo privilegio, y **sin `s3:DeleteObjectVersion` ni
`s3:BypassGovernanceRetention`**. Esa ausencia es lo que hace que `GOVERNANCE` proteja: el modo
permite saltarse la retención a quien tenga ese permiso, así que la aplicación no debe tenerlo. Con
él, la barrera 4 sería decorativa.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "LeerYEscribirObjetos",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:PutObjectRetention"
      ],
      "Resource": "arn:aws:s3:::tdd-evidencia-prod/*"
    },
    {
      "Sid": "SaberSiUnaClaveYaExiste",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::tdd-evidencia-prod"
    },
    {
      "Sid": "ComprobarQueElBucketSostieneLaBarrera4",
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketVersioning",
        "s3:GetBucketObjectLockConfiguration",
        "s3:GetBucketCORS"
      ],
      "Resource": "arn:aws:s3:::tdd-evidencia-prod"
    }
  ]
}
```

### Por qué está cada línea

| Acción | Por qué | Si falta |
|---|---|---|
| `s3:GetObject` | Leer originales y derivados. Cubre también `HEAD`, que es lo que usa `existe()` | No se ve ninguna fotografía |
| `s3:PutObject` | Subir | No se puede subir nada |
| **`s3:PutObjectRetention`** | La aplicación sube cada original con `ObjectLockMode` y `ObjectLockRetainUntilDate`. **Ese parámetro exige este permiso aparte** | **Falla cada subida de una fotografía, un documento o una plantilla**, con `AccessDenied`. Los derivados seguirían subiendo, así que parecería un fallo intermitente |
| **`s3:ListBucket`** | **Aunque la aplicación no liste nunca.** AWS **oculta la existencia** de los objetos a quien no puede listar: sin este permiso, un `HEAD` sobre una clave que no existe responde **403 y no 404**, para no revelar por el código de error lo que la política no deja ver. Y `guardar()` hace ese `HEAD` antes de cada original, para no sobrescribirlo | **Falla cada subida de original**, con un `AccessDenied` sobre `HeadObject` que no dice nada de todo esto. El adaptador traduce ese error y nombra el permiso, pero mejor no llegar ahí |
| Las tres de bucket | `AlmacenS3.comprobar()` las usa al arrancar para decir si la barrera 4 se sostiene | La aplicación arranca y avisa en cada arranque de que **no ha podido comprobarlo**, diciendo cuál falta. No es un fallo, pero se pierde la comprobación |

> **La primera versión de este documento no llevaba `s3:ListBucket`**, con el razonamiento de que la
> aplicación nunca lista: siempre conoce la clave exacta porque la construye con identificadores que
> tiene en la base. El razonamiento es correcto y la política **habría roto todas las subidas**, por
> lo del `403` de arriba. Se deja escrito porque es un error fácil de repetir: en S3, «no listar» y
> «no necesitar `ListBucket`» no son lo mismo.

`[REC]` `s3:ListBucket` permite enumerar las claves del bucket. Es el precio de poder comprobar la
existencia, y se acota al bucket concreto. Las claves son UUID sin significado, así que enumerarlas
no revela de qué encargo es cada cosa; el bucket sigue sin acceso público.

`s3:ListBucketVersions` **no** se le da a la aplicación: solo lo necesita
`tools/comprobar_almacen.py --escribir`, que se ejecuta a mano con credenciales de operación.

---

## 3. Comprobarlo antes de darlo por bueno

```bash
STORAGE_BACKEND=s3 STORAGE_BUCKET=tdd-evidencia-prod STORAGE_REGION=eu-west-1 \
APP_BASE_URL=https://tdd.sudominio.example \
  python3 tools/comprobar_almacen.py --escribir
```

Comprueba versionado, Object Lock, CORS **medido de verdad** —una petición con `Origin`, no la
configuración— y que S3 **rechaza borrar** la versión retenida de un original.

`[REQ]` Con `--escribir` sube un objeto que **no se va a poder borrar** durante los años que dure la
retención. Ejecútelo contra un bucket de pruebas creado igual que el de producción, o asuma que ese
objeto se queda ahí.

---

## 4. Lo que sigue sin comprobarse

`[LIM]` Nada de este documento se ha ejecutado contra AWS. Lo comprobado hasta ahora es:

| | Estado |
|---|---|
| El código del adaptador | Probado con `moto` |
| La barrera 4 contra un almacén real | Probada contra **MinIO**: rechaza borrar la versión retenida |
| Un bucket de **AWS** | **Sin comprobar** |
| Que `s3:PutObjectRetention` sea necesario | Deducido de la documentación de S3, **no verificado** |
| Que `s3:ListBucket` sea necesario para `HeadObject` | Deducido de la documentación de S3, **no verificado**. El adaptador traduce el `403` por si acaso |
| El comportamiento de CORS en AWS | **Sin comprobar** |

Media hora de alguien con credenciales y un bucket de pruebas cierra esta tabla entera.

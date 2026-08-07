"""API de autenticación.

`[REQ]` No hay ni un secreto en este fichero: la clave de firma viene de la
configuración y las contraseñas van con Argon2id.

**Estas rutas no usan `SesionDep`.** No pueden: `SesionDep` exige un token
válido, y aquí es donde se emite. Abren su propia sesión y fijan el contexto
RLS **en cuanto saben quién es el usuario**, que ocurre tras la búsqueda por
correo. Esa búsqueda es el único punto del sistema que se salta la RLS, y lo
hace con una función `SECURITY DEFINER` de alcance mínimo declarada en el
esquema.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.core.config import Settings
from tdd.core.db import ContextoRLS, aplicar_contexto
from tdd.core.deps import SesionDep, SettingsDep, UsuarioDep
from tdd.core.security import (
    crear_token,
    hash_password,
    necesita_rehash,
    verify_password,
)
from tdd.identity import recuperacion
from tdd.identity.service import (
    ClaveDebil,
    CredencialRechazada,
    MotivoDeRechazo,
    MotivoDeRevocacion,
    SesionGuardada,
    SesionNoValida,
    UsuarioParaLogin,
    ahora_utc,
    castigo_por_fallo,
    comprobar_fortaleza,
    comprobar_que_puede_entrar,
    comprobar_sesion_de_refresco,
    generar_token_de_refresco,
    huella_de,
)
from tdd.notificaciones.correo import Correo, Mensaje

router = APIRouter(prefix="/auth", tags=["Autenticación"])

#: Mensaje **único** para cualquier fallo de credencial. Distinguir «ese correo
#: no existe» de «esa contraseña no es» regala una lista de usuarios válidos.
MENSAJE_GENERICO = "Correo o contraseña incorrectos"

#: Hash de una contraseña que no es de nadie. Se verifica contra él cuando el
#: correo no existe, para que responder tarde lo mismo y el tiempo de respuesta
#: no delate qué cuentas hay. Se calcula una vez al arrancar.
_HASH_SEÑUELO = hash_password("contraseña-que-no-es-de-nadie-solo-para-igualar-tiempos")


class Credenciales(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, repr=False)


class Tokens(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 — es el tipo, no un secreto
    expires_in: int


class Refresco(BaseModel):
    refresh_token: str = Field(repr=False)


class CambioDeClave(BaseModel):
    current_password: str = Field(repr=False)
    new_password: str = Field(repr=False)


class Perfil(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    full_name: str
    org_role: str
    #: La marca explícita de la ficha. **No es el permiso efectivo.**
    can_manage_suggestions: bool
    #: `[REQ]` El permiso **efectivo** sobre el buzón, ya calculado.
    #:
    #: Lo publica el servidor para que la interfaz no lo vuelva a deducir. La
    #: regla «ADMIN o la marca» ya vivió repartida entre la API y la RLS y
    #: acabaron discrepando: un administrador sin la marca pasaba la
    #: comprobación y la base de datos le bloqueaba la escritura. Que el cliente
    #: la dedujera por su cuenta sería el tercer sitio donde puede desviarse.
    gestiona_sugerencias: bool


def _sesion_sin_contexto(request: Request) -> Session:
    return request.app.state.session_factory()  # type: ignore[no-any-return]


def _emitir(
    s: Session,
    *,
    settings: Settings,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    org_role: str,
    can_manage_suggestions: bool,
    family_id: uuid.UUID,
    request: Request,
) -> Tokens:
    """Crea el par de tokens y **guarda solo la huella** del de refresco."""
    ahora = ahora_utc()
    refresco = generar_token_de_refresco(ahora=ahora, dias=settings.refresh_token_ttl_days)
    s.execute(
        text(
            "INSERT INTO user_session (organization_id, user_id, refresh_token_hash, family_id, "
            "expires_at, user_agent) VALUES (:o, :u, :h, :f, :e, :ua) RETURNING id"
        ),
        {
            "o": str(organization_id),
            "u": str(user_id),
            "h": refresco.huella,
            "f": str(family_id),
            "e": refresco.expira_el,
            "ua": (request.headers.get("user-agent") or "")[:300] or None,
        },
    )
    acceso = crear_token(
        secreto=settings.app_secret_key,
        user_id=user_id,
        organization_id=organization_id,
        org_role=org_role,
        can_manage_suggestions=can_manage_suggestions,
        ttl_minutos=settings.access_token_ttl_minutes,
    )
    return Tokens(
        access_token=acceso,
        refresh_token=refresco.valor,
        expires_in=settings.access_token_ttl_minutes * 60,
    )


def _auditar(
    s: Session,
    *,
    organization_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    accion: str,
    severidad: str = "INFO",
) -> None:
    if organization_id is None:
        return  # Un correo desconocido no pertenece a ninguna organización.
    s.execute(
        text(
            "INSERT INTO audit_log (organization_id, actor_user_id, action, entity_type, "
            "entity_id, severity) VALUES (:o, :u, :a, 'app_user', :u, CAST(:s AS audit_severity))"
        ),
        {
            "o": str(organization_id),
            "u": str(user_id) if user_id else None,
            "a": accion,
            "s": severidad,
        },
    )


@router.post("/login", response_model=Tokens)
def iniciar_sesion(
    cuerpo: Credenciales, request: Request, response: Response, settings: SettingsDep
) -> Any:
    """Emite el par de tokens. Cualquier fallo devuelve el **mismo** `401`."""
    s = _sesion_sin_contexto(request)
    try:
        s.begin()
        fila = (
            s.execute(
                text(
                    "SELECT id, organization_id, password_hash, "
                    "CAST(org_role AS text) AS org_role, "
                    "can_manage_suggestions, is_active, failed_login_attempts, locked_until "
                    "FROM login_buscar_usuario(:e)"
                ),
                {"e": cuerpo.email},
            )
            .mappings()
            .first()
        )
        usuario = UsuarioParaLogin(**dict(fila)) if fila else None

        # Se verifica SIEMPRE, incluso sin usuario: si solo se verificara cuando
        # el correo existe, la diferencia de tiempo (Argon2 tarda ~50 ms) diría
        # qué correos están dados de alta.
        clave_ok = verify_password(
            cuerpo.password, usuario.password_hash if usuario else _HASH_SEÑUELO
        )

        ahora = ahora_utc()
        try:
            comprobar_que_puede_entrar(usuario, clave_correcta=clave_ok, ahora=ahora)
        except CredencialRechazada as exc:
            if usuario is not None:
                aplicar_contexto(
                    s, ContextoRLS(organization_id=usuario.organization_id, user_id=usuario.id)
                )
                if exc.motivo is MotivoDeRechazo.CREDENCIAL_INVALIDA:
                    castigo = castigo_por_fallo(usuario.failed_login_attempts, ahora=ahora)
                    s.execute(
                        text(
                            "UPDATE app_user SET failed_login_attempts = :n, locked_until = :h "
                            "WHERE id = :i"
                        ),
                        {"n": castigo.intentos, "h": castigo.bloqueado_hasta, "i": str(usuario.id)},
                    )
                    _auditar(
                        s,
                        organization_id=usuario.organization_id,
                        user_id=usuario.id,
                        accion="LOGIN_BLOCKED" if castigo.se_ha_bloqueado else "LOGIN_FAILED",
                        severidad="AVISO" if castigo.se_ha_bloqueado else "INFO",
                    )
                else:
                    _auditar(
                        s,
                        organization_id=usuario.organization_id,
                        user_id=usuario.id,
                        accion=f"LOGIN_REJECTED_{exc.motivo.value}",
                        severidad="AVISO",
                    )
            s.commit()
            # El bloqueo sí se dice: ocultarlo dejaría al usuario reintentando
            # sin entender por qué falla una contraseña que sabe correcta.
            if exc.motivo is MotivoDeRechazo.CUENTA_BLOQUEADA:
                minutos = max(exc.segundos_restantes // 60, 1)
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    f"Cuenta bloqueada temporalmente. Inténtelo de nuevo en {minutos} min",
                    headers={"Retry-After": str(exc.segundos_restantes)},
                ) from exc
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, MENSAJE_GENERICO) from exc

        assert usuario is not None  # noqa: S101 — garantizado por la comprobación anterior
        aplicar_contexto(
            s,
            ContextoRLS(
                organization_id=usuario.organization_id,
                user_id=usuario.id,
                can_manage_suggestions=usuario.can_manage_suggestions,
            ),
        )
        # Los parámetros recomendados de Argon2 suben con el tiempo. Rehashear
        # al entrar mantiene el coste al día sin pedirle nada al usuario.
        nuevo_hash = (
            hash_password(cuerpo.password) if necesita_rehash(usuario.password_hash) else None
        )
        s.execute(
            text(
                "UPDATE app_user SET failed_login_attempts = 0, locked_until = NULL, "
                "last_login_at = now(), password_hash = COALESCE(:h, password_hash) WHERE id = :i"
            ),
            {"h": nuevo_hash, "i": str(usuario.id)},
        )
        tokens = _emitir(
            s,
            settings=settings,
            user_id=usuario.id,
            organization_id=usuario.organization_id,
            org_role=usuario.org_role,
            can_manage_suggestions=usuario.can_manage_suggestions,
            family_id=uuid.uuid4(),
            request=request,
        )
        _auditar(
            s,
            organization_id=usuario.organization_id,
            user_id=usuario.id,
            accion="LOGIN_SUCCEEDED",
        )
        s.commit()
        response.headers["Cache-Control"] = "no-store"
        return tokens
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


@router.post("/refresh", response_model=Tokens)
def refrescar(cuerpo: Refresco, request: Request, settings: SettingsDep) -> Any:
    """Rota el token de refresco. **El anterior deja de valer inmediatamente.**"""
    s = _sesion_sin_contexto(request)
    try:
        s.begin()
        fila = (
            s.execute(
                text(
                    "SELECT id, user_id, organization_id, family_id, expires_at, revoked_at, "
                    "CAST(org_role AS text) AS org_role, can_manage_suggestions, is_active "
                    "FROM login_buscar_sesion(:h)"
                ),
                {"h": huella_de(cuerpo.refresh_token)},
            )
            .mappings()
            .first()
        )
        sesion = SesionGuardada(**dict(fila)) if fila else None
        try:
            comprobar_sesion_de_refresco(sesion, ahora=ahora_utc())
        except SesionNoValida as exc:
            if exc.revocar_familia and sesion is not None:
                aplicar_contexto(
                    s,
                    ContextoRLS(organization_id=sesion.organization_id, user_id=sesion.user_id),
                )
                s.execute(
                    text(
                        "UPDATE user_session SET revoked_at = now(), revoked_reason = :r "
                        "WHERE family_id = :f AND revoked_at IS NULL"
                    ),
                    {"r": MotivoDeRevocacion.REUTILIZACION.value, "f": str(sesion.family_id)},
                )
                _auditar(
                    s,
                    organization_id=sesion.organization_id,
                    user_id=sesion.user_id,
                    accion="REFRESH_TOKEN_REUSED",
                    severidad="CRITICO",
                )
                s.commit()
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión no válida") from exc

        assert sesion is not None  # noqa: S101
        aplicar_contexto(
            s,
            ContextoRLS(
                organization_id=sesion.organization_id,
                user_id=sesion.user_id,
                can_manage_suggestions=sesion.can_manage_suggestions,
            ),
        )
        tokens = _emitir(
            s,
            settings=settings,
            user_id=sesion.user_id,
            organization_id=sesion.organization_id,
            org_role=sesion.org_role,
            can_manage_suggestions=sesion.can_manage_suggestions,
            family_id=sesion.family_id,
            request=request,
        )
        s.execute(
            text("UPDATE user_session SET revoked_at = now(), revoked_reason = :r WHERE id = :i"),
            {"r": MotivoDeRevocacion.ROTADA.value, "i": str(sesion.id)},
        )
        s.commit()
        return tokens
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def cerrar_sesion(cuerpo: Refresco, s: SesionDep, usuario: UsuarioDep) -> None:
    """Revoca el token de refresco presentado.

    El token de acceso sigue valiendo hasta caducar (15 minutos): revocarlo
    exigiría consultar la base en cada petición, que es justo lo que un token
    firmado evita. El compromiso es explícito y el TTL, corto.
    """
    s.execute(
        text(
            "UPDATE user_session SET revoked_at = now(), revoked_reason = :r "
            "WHERE refresh_token_hash = :h AND user_id = :u AND revoked_at IS NULL"
        ),
        {
            "r": MotivoDeRevocacion.CIERRE_DE_SESION.value,
            "h": huella_de(cuerpo.refresh_token),
            "u": str(usuario.id),
        },
    )


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def cerrar_todas_las_sesiones(s: SesionDep, usuario: UsuarioDep) -> None:
    """«He perdido el móvil.» Cierra todo, incluida esta sesión."""
    s.execute(
        text(
            "UPDATE user_session SET revoked_at = now(), revoked_reason = :r "
            "WHERE user_id = :u AND revoked_at IS NULL"
        ),
        {"r": MotivoDeRevocacion.CIERRE_DE_SESION.value, "u": str(usuario.id)},
    )


@router.get("/me", response_model=Perfil)
def quien_soy(s: SesionDep, usuario: UsuarioDep) -> Any:
    fila = (
        s.execute(
            text(
                "SELECT id, organization_id, email, full_name, CAST(org_role AS text) AS org_role, "
                "can_manage_suggestions FROM app_user WHERE id = :i"
            ),
            {"i": str(usuario.id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return {**dict(fila), "gestiona_sugerencias": usuario.gestiona_sugerencias}


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def cambiar_clave(cuerpo: CambioDeClave, s: SesionDep, usuario: UsuarioDep) -> None:
    """Cambia la contraseña y **cierra todas las demás sesiones**.

    Si alguien cambia su contraseña es porque sospecha, o porque se lo han
    pedido. Dejar vivas las sesiones abiertas convertiría el cambio en un
    gesto vacío.
    """
    fila = s.execute(
        text("SELECT password_hash, email FROM app_user WHERE id = :i"), {"i": str(usuario.id)}
    ).first()
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    if not verify_password(cuerpo.current_password, fila.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "La contraseña actual no es correcta")
    try:
        comprobar_fortaleza(cuerpo.new_password, email=fila.email)
    except ClaveDebil as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    if verify_password(cuerpo.new_password, fila.password_hash):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "La nueva contraseña no puede ser la actual"
        )

    s.execute(
        text(
            "UPDATE app_user SET password_hash = :h, password_changed_at = now(), "
            "failed_login_attempts = 0, locked_until = NULL WHERE id = :i"
        ),
        {"h": hash_password(cuerpo.new_password), "i": str(usuario.id)},
    )
    s.execute(
        text(
            "UPDATE user_session SET revoked_at = now(), revoked_reason = :r "
            "WHERE user_id = :u AND revoked_at IS NULL"
        ),
        {"r": MotivoDeRevocacion.CAMBIO_DE_CLAVE.value, "u": str(usuario.id)},
    )
    _auditar(
        s,
        organization_id=usuario.organization_id,
        user_id=usuario.id,
        accion="PASSWORD_CHANGED",
        severidad="AVISO",
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Recuperación de contraseña `[REQ]` §10.2
# ─────────────────────────────────────────────────────────────────────────────


def obtener_correo(request: Request) -> Correo:
    """Lo aporta la aplicación. Por defecto **no envía: registra que no envía**."""
    return request.app.state.correo  # type: ignore[no-any-return]


CorreoDep = Annotated[Correo, Depends(obtener_correo)]


class PeticionDeRecuperacion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class RespuestaDeRecuperacion(BaseModel):
    #: `[REQ]` Siempre la misma frase, exista o no la cuenta.
    detail: str = recuperacion.RESPUESTA_UNICA


ASUNTO = "Restablecer su contraseña"

CUERPO = """Hola{saludo}:

Alguien ha pedido restablecer la contraseña de esta cuenta en la aplicación de
due diligence técnica. Si ha sido usted, abra este enlace:

  {enlace}

El enlace caduca en 30 minutos y solo se puede usar una vez.

Si no ha sido usted, no hace falta que haga nada: la contraseña actual sigue
siendo válida y este enlace dejará de servir solo. Si le llegan varios de estos
correos sin haberlos pedido, avise a un administrador de su organización.
"""


@router.post(
    "/password/forgot",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RespuestaDeRecuperacion,
)
def olvide_mi_clave(
    cuerpo: PeticionDeRecuperacion,
    request: Request,
    settings: SettingsDep,
    correo: CorreoDep,
) -> Any:
    """`[REQ]` §10.2 · Responde `202` **siempre**, exista o no la dirección.

    Un formulario de «he olvidado mi contraseña» que distingue entre «enviado»
    y «ese correo no existe» es un comprobador de cuentas gratuito: se prueba
    una lista de direcciones y se sabe cuáles pertenecen a la organización.

    `[LIM]` Queda una diferencia de **tiempo**: cuando la cuenta existe hay que
    hablar con el servidor SMTP y eso tarda. Lo correcto es encolar el envío y
    responder igual de rápido en los dos casos, y para eso hace falta el worker
    asíncrono de §17, que no está construido. Mientras tanto lo que acota el
    abuso es el límite por usuario, que además evita usar esto para llenarle el
    buzón a alguien.
    """
    s = _sesion_sin_contexto(request)
    try:
        s.begin()
        fila = (
            s.execute(
                text(
                    "SELECT id, organization_id, full_name, is_active FROM reset_buscar_usuario(:e)"
                ),
                {"e": cuerpo.email},
            )
            .mappings()
            .first()
        )

        # El token se genera SIEMPRE, aunque no haya a quién mandárselo: es
        # barato y evita que la rama «existe» haga trabajo que la otra no.
        token = recuperacion.generar(ahora=ahora_utc())

        if fila is not None and fila["is_active"]:
            aplicar_contexto(
                s,
                ContextoRLS(
                    organization_id=fila["organization_id"],
                    user_id=fila["id"],
                    can_manage_suggestions=False,
                ),
            )
            desde = ahora_utc() - timedelta(minutes=recuperacion.MINUTOS_DE_VENTANA)
            recientes = s.execute(
                text("SELECT reset_peticiones_recientes(:u, :d)"),
                {"u": str(fila["id"]), "d": desde},
            ).scalar_one()

            if recuperacion.se_debe_enviar(int(recientes)):
                s.execute(
                    text("SELECT reset_crear(:o, :u, :h, :e, :ip, :ag)"),
                    {
                        "o": str(fila["organization_id"]),
                        "u": str(fila["id"]),
                        "h": token.huella,
                        "e": token.expira_el,
                        "ip": recuperacion.ip_valida(
                            request.client.host if request.client else None
                        ),
                        "ag": request.headers.get("user-agent", ""),
                    },
                )
                _auditar(
                    s,
                    organization_id=fila["organization_id"],
                    user_id=fila["id"],
                    accion="PASSWORD_RESET_REQUESTED",
                    severidad="AVISO",
                )
                s.commit()
                # Se envía DESPUÉS de confirmar. Si el correo falla, el token ya
                # está guardado y quien lo recibiera podría usarlo; al revés
                # —enviar y luego fallar al guardar— dejaría en circulación un
                # enlace que la base no reconoce.
                correo.enviar(
                    Mensaje(
                        destinatario=cuerpo.email,
                        asunto=ASUNTO,
                        cuerpo=CUERPO.format(
                            saludo=f", {fila['full_name'].split()[0]}" if fila["full_name"] else "",
                            enlace=recuperacion.enlace(settings.app_base_url, token.valor),
                        ),
                    )
                )
            else:
                # Pasado el tope no se manda otro correo, pero la respuesta no
                # cambia: cambiarla volvería a delatar qué cuentas existen.
                _auditar(
                    s,
                    organization_id=fila["organization_id"],
                    user_id=fila["id"],
                    accion="PASSWORD_RESET_THROTTLED",
                    severidad="AVISO",
                )
                s.commit()
        else:
            s.rollback()
        return {"detail": recuperacion.RESPUESTA_UNICA}
    finally:
        s.close()


class Restablecimiento(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1)


@router.post("/password/reset", status_code=status.HTTP_204_NO_CONTENT)
def restablecer_clave(cuerpo: Restablecimiento, request: Request) -> Response:
    """`[REQ]` Cambia la contraseña, gasta el token y **cierra todas las sesiones**.

    Lo último no es un extra. Quien recupera su contraseña suele hacerlo porque
    ha perdido el acceso o porque sospecha: dejar vivas las sesiones abiertas
    mantendría dentro exactamente a quien se quiere echar.

    Las cuatro operaciones van en `reset_consumir`, una sola sentencia, para que
    no haya un instante en que el token ya sirvió y todavía se pueda reutilizar.
    """
    s = _sesion_sin_contexto(request)
    try:
        s.begin()
        fila = (
            s.execute(
                text(
                    "SELECT id, user_id, organization_id, email, expires_at, used_at, is_active "
                    "FROM reset_buscar_token(:h)"
                ),
                {"h": recuperacion.huella_de(cuerpo.token)},
            )
            .mappings()
            .first()
        )
        guardado = (
            recuperacion.TokenGuardado(
                expira_el=fila["expires_at"],
                usado_el=fila["used_at"],
                cuenta_activa=fila["is_active"],
            )
            if fila
            else None
        )
        try:
            recuperacion.comprobar(guardado, ahora=ahora_utc())
        except recuperacion.TokenRechazado as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

        assert fila is not None  # noqa: S101 — `comprobar` ya ha lanzado si no
        try:
            comprobar_fortaleza(cuerpo.new_password, email=fila["email"])
        except ClaveDebil as exc:
            # 422 y no 400: el enlace es bueno, la contraseña no. Y el token NO
            # se gasta, para que se pueda reintentar con otra sin pedir otro
            # correo.
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

        aplicar_contexto(
            s,
            ContextoRLS(
                organization_id=fila["organization_id"],
                user_id=fila["user_id"],
                can_manage_suggestions=False,
            ),
        )
        s.execute(
            text("SELECT reset_consumir(:t, :h)"),
            {"t": str(fila["id"]), "h": hash_password(cuerpo.new_password)},
        )
        _auditar(
            s,
            organization_id=fila["organization_id"],
            user_id=fila["user_id"],
            accion="PASSWORD_RESET_COMPLETED",
            severidad="AVISO",
        )
        s.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    finally:
        s.close()

import logging

import requests
from django.conf import settings

from .errores import traducir_mensaje_drf

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Error de la API, ya limpio para mostrar al usuario.

    ``message`` es solo el texto de ``error`` de la API (nunca incluye
    la clave ``codigo``); ``codigo`` es la clave estable de la API (por
    ejemplo "validacion" o "borrado_protegido") para decidir qué hacer,
    y ``detalles`` es la lista de mensajes por campo de un 400, para
    decir qué corregir.
    """

    def __init__(self, message, status_code=None, codigo=None, detalles=None):
        super().__init__(message)
        self.status_code = status_code
        self.codigo = codigo
        self.detalles = list(detalles) if detalles else []


class SesionCaducada(APIError):
    """La API devolvió 401: el token ya no vale.

    La levanta `api_error()` en vez de mostrar el error en la página: quien
    la recoge redirige a login con el mensaje de sesión caducada.
    """

    def __init__(self, message="Tu sesión caducó. Inicia sesión de nuevo."):
        super().__init__(message, status_code=401)


def _aplanar_detalles(detalles):
    """Convierte `detalles` de un error 400 en mensajes "campo: texto".

    La API devuelve `detalles` como diccionario por campo (el detalle de
    un ValidationError de DRF) o como lista de mensajes. Se traduce lo
    conocido y se aplana a una lista de textos, sin llaves ni claves
    técnicas: es lo que se usa para decir qué campo corregir.
    """
    mensajes = []
    if isinstance(detalles, dict):
        for campo, errs in detalles.items():
            if not isinstance(errs, list):
                errs = [errs]
            for err in errs:
                if isinstance(err, dict):
                    mensajes.extend(_aplanar_detalles(err))
                    continue
                texto = traducir_mensaje_drf(err)
                if campo in ("non_field_errors", "__all__"):
                    mensajes.append(texto)
                else:
                    mensajes.append(f"{campo}: {texto}")
        return mensajes
    if isinstance(detalles, list):
        for item in detalles:
            mensajes.extend(_aplanar_detalles(item))
        return mensajes
    if detalles is None:
        return []
    texto = str(detalles).strip()
    return [traducir_mensaje_drf(texto)] if texto else []


def _aplanar_errores(error_data):
    """Convierte el cuerpo de error de la API en una lista de mensajes.

    DRF devuelve dicts como {"campo": ["mensaje", ...]} o
    {"non_field_errors": [...]}, y a veces {"detail": "..."}. Se aplana a
    texto, se traduce lo conocido y nunca se muestra el dict tal cual
    (antes el login mostraba el dict entero, llaves incluidas).

    Las claves "codigo" y "detalles" del formato nuevo de la API no son
    mensajes: "codigo" es solo para la lógica y "detalles" se extrae
    aparte, así que aquí se saltan.
    """
    mensajes = []
    if isinstance(error_data, dict):
        for campo, errs in error_data.items():
            if campo in ("codigo", "detalles"):
                continue
            if isinstance(errs, dict):
                for subcampo, suberrs in errs.items():
                    mensajes.extend(_aplanar_errores({f"{campo}.{subcampo}": suberrs}))
                continue
            if not isinstance(errs, list):
                errs = [errs]
            texto = " ".join(traducir_mensaje_drf(e) for e in errs)
            if campo in ("detail", "non_field_errors"):
                mensajes.append(texto)
            else:
                mensajes.append(f"{campo}: {texto}")
        return mensajes
    if isinstance(error_data, list):
        for item in error_data:
            mensajes.extend(_aplanar_errores(item))
        return mensajes
    texto = str(error_data).strip()
    return [traducir_mensaje_drf(texto)] if texto else []


def _extraer_error_api(error_data):
    """(mensaje, codigo, detalles) del cuerpo de error de la API.

    Formato nuevo de la API (su PR #6): {"error": "...", "codigo": "..."}
    y en los 400 además "detalles" (por campo o lista). Se muestra solo
    "error": "codigo" es una clave para la lógica, no para el usuario
    (antes se mostraba "error: ... | codigo: ..."), y "detalles" va
    aparte para decir qué campo corregir. El formato viejo de DRF
    (dict por campo, "detail", ...) sigue funcionando igual.
    """
    if isinstance(error_data, dict) and "error" in error_data:
        mensaje = str(error_data.get("error") or "").strip()
        codigo = error_data.get("codigo")
        detalles = _aplanar_detalles(error_data.get("detalles"))
        if not mensaje:
            mensaje = "La API devolvió un error."
        return mensaje, codigo, detalles
    if isinstance(error_data, dict):
        detalles = _aplanar_detalles(error_data.get("detalles"))
        mensajes = _aplanar_errores(error_data)
        mensaje = " | ".join(mensajes) if mensajes else ""
        return mensaje, error_data.get("codigo"), detalles
    mensajes = _aplanar_errores(error_data)
    return (" | ".join(mensajes) if mensajes else ""), None, []


def _detalle_error(response):
    """Mensaje, código y detalles limpios del error de una respuesta HTTP.

    Sin códigos ni detalles internos en el mensaje: lo que se muestra al
    usuario es el mensaje; el código y los detalles van en la excepción
    para que la vista decida qué hacer. El detalle técnico queda en el
    registro (ver logger).
    """
    try:
        error_data = response.json()
    except ValueError:
        error_data = response.text.strip() or response.reason
    mensaje, codigo, detalles = _extraer_error_api(error_data)
    if not mensaje:
        mensaje = f"La API respondió {response.status_code}."
    return mensaje, codigo, detalles


class MikrotikAPIClient:
    def __init__(self, token=None):
        self.base_url = settings.MIKROTIK_API_URL.rstrip("/")
        self.timeout = settings.MIKROTIK_API_TIMEOUT
        self.headers = {"Accept": "application/json"}
        configured_token = settings.MIKROTIK_API_TOKEN if token is None else token
        if configured_token:
            self.headers["Authorization"] = "Token " + configured_token

        self.username = settings.MIKROTIK_API_USERNAME
        self.password = settings.MIKROTIK_API_PASSWORD
        self._authentication_attempted = False

    def _url(self, path):
        return f"{self.base_url}/{path.lstrip('/')}"

    def request(self, method, path, **kwargs):
        # 1. Intentar autenticar preventivamente si hay credenciales y no hay token
        if (
            "Authorization" not in self.headers
            and self.username
            and self.password
            and not self._authentication_attempted
        ):
            self._authenticate()

        # 2. Ejecutar la petición
        try:
            response = requests.request(
                method,
                self._url(path),
                headers=self.headers,
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            # El texto crudo de requests (host, puerto, "Max retries...") es
            # técnico y en inglés: solo va al registro, no al usuario.
            logger.warning("No se pudo conectar con la API (%s %s): %s", method, path, exc)
            raise APIError("No se pudo conectar con la API.") from exc

        # 3. REINTENTO AUTOMÁTICO: Si da 401 (Unauthorized) y tenemos credenciales, reautenticar una vez
        if response.status_code == 401 and self.username and self.password and not self._authentication_attempted:
            self._authenticate()
            try:
                response = requests.request(
                    method,
                    self._url(path),
                    headers=self.headers,
                    timeout=self.timeout,
                    **kwargs,
                )
            except requests.RequestException as exc:
                logger.warning(
                    "No se pudo conectar con la API tras reautenticar (%s %s): %s",
                    method,
                    path,
                    exc,
                )
                raise APIError("No se pudo conectar con la API.") from exc

        # 4. Manejo de errores HTTP
        if response.status_code >= 400:
            mensaje, codigo, detalles = _detalle_error(response)
            logger.warning(
                "La API respondió %s en %s %s: %s",
                response.status_code,
                method,
                path,
                mensaje,
            )
            raise APIError(
                mensaje,
                status_code=response.status_code,
                codigo=codigo,
                detalles=detalles,
            )

        if response.status_code == 204:
            return None

        try:
            return response.json()
        except ValueError as exc:
            logger.warning("La API devolvió una respuesta que no es JSON en %s %s.", method, path)
            raise APIError("La API devolvió una respuesta que no es JSON.") from exc

    def _authenticate(self):
        self._authentication_attempted = True
        return self.login(self.username, self.password)

    def login(self, username, password):
        try:
            response = requests.request(
                "POST",
                self._url("token/"),
                headers={"Accept": "application/json"},
                timeout=self.timeout,
                json={"username": username, "password": password},
            )
        except requests.RequestException as exc:
            logger.warning("No se pudo conectar con la API al iniciar sesión: %s", exc)
            raise APIError("No se pudo conectar con la API.") from exc

        if response.status_code >= 400:
            mensaje, codigo, detalles = _detalle_error(response)
            logger.warning("La autenticación de la API falló (%s): %s", response.status_code, mensaje)
            raise APIError(
                mensaje,
                status_code=response.status_code,
                codigo=codigo,
                detalles=detalles,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise APIError("La API de autenticación no devolvió una respuesta JSON.") from exc

        token = data.get("token") or data.get("key")
        if not token:
            raise APIError("La API no devolvió un token de autenticación.")
        self.headers["Authorization"] = "Token " + str(token)
        return data

    def get_list(self, path):
        data = self.request("GET", path)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("results", "items", "data"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []

    # Rutas candidatas para revocar el token DRF, en orden. La API ya tiene
    # POST /api/token/revocar/ (desde su preparación para producción); se
    # mantiene POST /api/logout/ como alternativa por compatibilidad. Si la
    # API responde 404/405 en todas, se devuelve False y quien llama solo
    # limpia la sesión local. Si la API termina usando otra ruta, basta con
    # cambiar esta tupla. Un 401 significa que el token ya no vale, así que
    # también cuenta como revocado.
    RUTAS_REVOCACION_TOKEN = ("token/revocar/", "logout/")

    def revocar_token(self):
        for ruta in self.RUTAS_REVOCACION_TOKEN:
            try:
                self.post(ruta)
                return True
            except APIError as exc:
                if exc.status_code in (404, 405):
                    continue
                if exc.status_code == 401:
                    return True
                raise
        return False

    def get(self, path):
        return self.request("GET", path)

    def post(self, path, data=None):
        return self.request("POST", path, json=data or {})

    def patch(self, path, data):
        return self.request("PATCH", path, json=data)

    def put(self, path, data):
        return self.request("PUT", path, json=data)

    def delete(self, path):
        return self.request("DELETE", path)

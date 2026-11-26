import logging

import requests
from django.conf import settings

from .errores import traducir_mensaje_drf

logger = logging.getLogger(__name__)


class APIError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class SesionCaducada(APIError):
    """La API devolvió 401: el token ya no vale.

    La levanta `api_error()` en vez de mostrar el error en la página: quien
    la recoge redirige a login con el mensaje de sesión caducada.
    """

    def __init__(self, message="Tu sesión caducó. Inicia sesión de nuevo."):
        super().__init__(message, status_code=401)


def _aplanar_errores(error_data):
    """Convierte el cuerpo de error de la API en una lista de mensajes.

    DRF devuelve dicts como {"campo": ["mensaje", ...]} o
    {"non_field_errors": [...]}, y a veces {"detail": "..."}. Se aplana a
    texto, se traduce lo conocido y nunca se muestra el dict tal cual
    (antes el login mostraba el dict entero, llaves incluidas).
    """
    mensajes = []
    if isinstance(error_data, dict):
        for campo, errs in error_data.items():
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


def _detalle_error(response):
    """Texto limpio del error de una respuesta HTTP de la API.

    Sin códigos ni detalles internos: el mensaje que se muestra al usuario
    es este; el detalle técnico queda en el registro (ver logger).
    """
    try:
        error_data = response.json()
    except ValueError:
        error_data = response.text.strip() or response.reason
    mensajes = _aplanar_errores(error_data)
    if mensajes:
        return " | ".join(mensajes)
    return f"La API respondió {response.status_code}."


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
            detalle = _detalle_error(response)
            logger.warning(
                "La API respondió %s en %s %s: %s",
                response.status_code,
                method,
                path,
                detalle,
            )
            raise APIError(
                detalle,
                status_code=response.status_code,
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
            detalle = _detalle_error(response)
            logger.warning("La autenticación de la API falló (%s): %s", response.status_code, detalle)
            raise APIError(
                detalle,
                status_code=response.status_code,
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

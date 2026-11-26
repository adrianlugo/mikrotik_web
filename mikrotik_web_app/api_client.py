import requests
from django.conf import settings


class APIError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


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
            raise APIError(f"No se pudo conectar con la API: {exc}") from exc

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
                raise APIError(f"No se pudo conectar con la API tras reautenticar: {exc}") from exc

        # 4. Manejo de errores HTTP
        if response.status_code >= 400:
            try:
                error_data = response.json()
            except ValueError:
                error_data = response.text.strip() or response.reason

            # Si la API devuelve un diccionario de errores (ej. por campos)
            if isinstance(error_data, dict):
                mensajes = []
                for campo, errs in error_data.items():
                    if isinstance(errs, list):
                        err_str = " ".join(str(e) for e in errs)
                    else:
                        err_str = str(errs)
                    # Si la clave es 'detail', lo mostramos directo; si no, indicamos el campo
                    if campo == "detail":
                        mensajes.append(err_str)
                    else:
                        mensajes.append(f"{campo}: {err_str}")
                detail = " | ".join(mensajes) if mensajes else str(error_data)
            else:
                detail = str(error_data)

            raise APIError(
                detail,  # Devolvemos directamente el texto limpio sin el "La API respondió 400:"
                status_code=response.status_code,
            )

        if response.status_code == 204:
            return None
            
        try:
            return response.json()
        except ValueError as exc:
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
            raise APIError(f"No se pudo autenticar con la API: {exc}") from exc

        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text.strip() or response.reason
            raise APIError(
                f"La autenticación de la API falló ({response.status_code}): {detail}",
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

    # Rutas candidatas para revocar el token DRF, en orden. La API aún no
    # tiene endpoint de revocación (lo está añadiendo otro trabajo en
    # paralelo): si responde 404/405 en todas, se devuelve False y quien
    # llama solo limpia la sesión local. Si la API termina usando otra
    # ruta, basta con cambiar esta tupla. Un 401 significa que el token
    # ya no vale, así que también cuenta como revocado.
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

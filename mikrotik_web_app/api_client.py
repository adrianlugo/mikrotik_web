import requests
from django.conf import settings


class APIError(Exception):
    pass


class MikrotikAPIClient:
    def __init__(self):
        self.base_url = settings.MIKROTIK_API_URL.rstrip("/")
        self.timeout = settings.MIKROTIK_API_TIMEOUT
        self.headers = {"Accept": "application/json"}
        if settings.MIKROTIK_API_TOKEN:
            self.headers["Authorization"] = f"Bearer {settings.MIKROTIK_API_TOKEN}"

        self.auth = None
        if settings.MIKROTIK_API_USERNAME and settings.MIKROTIK_API_PASSWORD:
            self.auth = (
                settings.MIKROTIK_API_USERNAME,
                settings.MIKROTIK_API_PASSWORD,
            )

    def _url(self, path):
        return f"{self.base_url}/{path.lstrip('/')}"

    def request(self, method, path, **kwargs):
        try:
            response = requests.request(
                method,
                self._url(path),
                headers=self.headers,
                auth=self.auth,
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise APIError(f"No se pudo conectar con la API: {exc}") from exc

        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text.strip() or response.reason
            raise APIError(f"La API respondió {response.status_code}: {detail}")

        if response.status_code == 204:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise APIError("La API devolvió una respuesta que no es JSON.") from exc

    def get_list(self, path):
        data = self.request("GET", path)
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            return data["results"]
        return data if isinstance(data, list) else []

    def get(self, path):
        return self.request("GET", path)

    def post(self, path, data=None):
        return self.request("POST", path, json=data or {})

    def patch(self, path, data):
        return self.request("PATCH", path, json=data)

    def delete(self, path):
        return self.request("DELETE", path)

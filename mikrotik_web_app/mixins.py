from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from .api_client import MikrotikAPIClient
from .utils import clear_api_session, _related_id, _related_form_id


class APIViewMixin:
    @staticmethod
    def _normalize_router(router):
        if not isinstance(router, dict):
            return router

        normalized = dict(router)
        aliases = {
            "nombre": ("name", "nombre"),
            "name": ("name", "nombre"),
            "ip_address": ("ip_address", "ip"),
            "ip": ("ip_address", "ip"),
            "modelo": ("model", "modelo"),
            "model": ("model", "modelo"),
            "ubicacion": ("location", "ubicacion"),
            "location": ("location", "ubicacion"),
        }
        for canonical, keys in aliases.items():
            if normalized.get(canonical) is None:
                normalized[canonical] = next(
                    (normalized[key] for key in keys if normalized.get(key) not in (None, "")),
                    "",
                )
        return normalized

    def normalize_routers(self, routers):
        return [self._normalize_router(router) for router in routers]

    @staticmethod
    def _normalize_plan(plan):
        if not isinstance(plan, dict):
            return plan

        normalized = dict(plan)
        normalized["display_name"] = next(
            (
                normalized[key]
                for key in ("nombre_perfil", "nombre", "name")
                if normalized.get(key) not in (None, "")
            ),
            "Plan sin nombre",
        )
        normalized["router"] = _related_id(normalized.get("router"))
        normalized["velocidad_subida_mostrada"] = normalized.get("subida_mbps")
        normalized["velocidad_descarga_mostrada"] = normalized.get("bajada_mbps")
        return normalized

    def normalize_plans(self, plans):
        return [self._normalize_plan(plan) for plan in plans]

    def api(self, request=None):
        request = request or getattr(self, "request", None)
        token = None
        if request is not None:
            token = request.session.get("mikrotik_api_token")
        return MikrotikAPIClient(token=token)

    def api_error(self, request, exc):
        if exc.status_code == 401:
            clear_api_session(request)
        messages.error(request, str(exc))


class AuthenticatedAPIViewMixin(APIViewMixin):
    def dispatch(self, request, *args, **kwargs):
        has_configured_token = bool(settings.MIKROTIK_API_TOKEN)
        has_configured_credentials = bool(
            settings.MIKROTIK_API_USERNAME and settings.MIKROTIK_API_PASSWORD
        )
        has_session_token = bool(request.session.get("mikrotik_api_token"))

        if not (has_configured_token or has_configured_credentials or has_session_token):
            return redirect("login")
        return super().dispatch(request, *args, **kwargs)


class PlanFormMixin(APIViewMixin):
    @staticmethod
    def normalize_form_data(data):
        normalized = dict(data)
        normalized["router_id"] = _related_form_id(data.get("router"))
        return normalized

    def build_payload(self, data):
        nombre = data.get("nombre_perfil", "").strip()
        cola_padre = data.get("cola_padre", "").strip()
        if not nombre:
            raise ValueError("Ingrese el nombre del perfil PPPoE.")

        try:
            router = int(data["router"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Seleccione un router válido.") from None

        try:
            subida = int(data["subida_mbps"])
            bajada = int(data["bajada_mbps"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Ingrese las velocidades de subida y bajada.") from None

        if subida <= 0 or bajada <= 0:
            raise ValueError("Las velocidades deben ser mayores que cero.")

        return {
            "nombre_perfil": nombre,
            "cola_padre": cola_padre,
            "subida_mbps": subida,
            "bajada_mbps": bajada,
            "router": router,
        }


class RouterFormMixin(APIViewMixin):
    @staticmethod
    def normalize_form_data(data):
        normalized = dict(data)
        normalized["activo_checked"] = data.get("activo") in (
            True,
            "true",
            "True",
            "on",
            "1",
            1,
        )
        normalized["puerto_api"] = normalized.get("puerto_api") or 8728
        return normalized

    def build_payload(self, data, partial=False):
        nombre = data.get("nombre", "").strip()
        ip_address = data.get("ip_address", "").strip()
        usuario = data.get("usuario", "").strip()
        password = data.get("password", "")
        activo = data.get("activo") in ("on", "true", "True", "1", True, 1)

        if not nombre:
            raise ValueError("Ingrese el nombre del router.")
        if not ip_address:
            raise ValueError("Ingrese la dirección IP del router.")
        if not usuario:
            raise ValueError("Ingrese el usuario API.")
        try:
            puerto_api = int(data.get("puerto_api", 8728))
        except (TypeError, ValueError):
            raise ValueError("Ingrese un puerto API válido.") from None
        if puerto_api <= 0:
            raise ValueError("El puerto API debe ser mayor que cero.")
        if not partial and not password:
            raise ValueError("Ingrese la contraseña API.")

        payload = {
            "nombre": nombre,
            "ip_address": ip_address,
            "puerto_api": puerto_api,
            "usuario": usuario,
            "activo": activo,
        }
        if password:
            payload["password"] = password
        return payload


class ClienteRedFormMixin:
    @staticmethod
    def _related_id(value):
        if isinstance(value, dict):
            return value.get("id") or value.get("pk")
        return value

    @staticmethod
    def normalize_plans(plans):
        normalized_plans = []
        for plan in plans:
            if not isinstance(plan, dict):
                normalized_plans.append(plan)
                continue
            normalized = dict(plan)
            normalized["display_name"] = next(
                (
                    normalized[key]
                    for key in ("nombre_perfil", "nombre", "name")
                    if normalized.get(key) not in (None, "")
                ),
                "Plan sin nombre",
            )
            normalized_plans.append(normalized)
        return normalized_plans

    def normalize_form_data(self, data):
        normalized = dict(data)
        normalized["plan_id"] = self._related_id(data.get("plan"))
        normalized["router_id"] = self._related_id(data.get("router"))
        return normalized

    def get_catalogs(self, api):
        return {
            "planes": self.normalize_plans(api.get_list("planes/")),
            "routers": self.normalize_routers(api.get_list("routers/")),
        }

    def build_payload(self, data, partial=False):
        payload = {
            "nombre": data.get("nombre", "").strip(),
            "tipo": data.get("tipo", "dhcp"),
            "direccion_ip": data.get("direccion_ip", "").strip(),
            "direccion_mac": data.get("direccion_mac", "").strip(),
            "interfaz_mikrotik": data.get("interfaz_mikrotik", "").strip(),
            "servidor_dhcp": data.get("servidor_dhcp", "").strip(),
            "estado": data.get("estado", "activo"),
        }
        if not partial:
            payload.update(
                plan=int(data["plan"]),
                router=int(data["router"]),
            )
        return payload
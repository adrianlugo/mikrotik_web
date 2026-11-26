from datetime import date

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from .api_client import MikrotikAPIClient
from .utils import _decimal, clear_api_session, _related_id, _related_form_id


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
        if getattr(exc, "status_code", None) == 401:
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

    @staticmethod
    def get_colas_por_router(api, routers):
        """Colas simples por router para el desplegable de cola padre.

        Lee GET routers/{id}/colas/ de la API. Si la API no responde, el
        router no tiene colas o la API es anterior a ese endpoint, devuelve
        lista vacía para ese router: el formulario sigue funcionando y
        dejar la cola vacía hace que la API genere Plan-{perfil}.
        """
        colas_por_router = {}
        for router in routers or []:
            router_id = _related_id(router.get("id")) if isinstance(router, dict) else router
            if router_id is None:
                continue
            try:
                data = api.get(f"routers/{router_id}/colas/")
                colas = data.get("colas") if isinstance(data, dict) else None
            except Exception:
                colas = None
            if not isinstance(colas, list):
                colas = []
            colas_por_router[str(router_id)] = [
                {
                    "nombre": cola.get("nombre") or cola.get("name"),
                    "target": cola.get("target") or "",
                    "max_limit": cola.get("max-limit") or cola.get("max_limit") or "",
                    "parent": cola.get("parent") or "",
                }
                for cola in colas
                if isinstance(cola, dict) and (cola.get("nombre") or cola.get("name"))
            ]
        return colas_por_router

    def build_payload(self, data):
        # Limpieza básica de texto
        nombre = data.get("nombre_perfil", "").strip()
        cola_padre = data.get("cola_padre", "").strip()
        
        if not nombre:
            raise ValueError("Ingrese el nombre del perfil PPPoE.")

        # Conversiones básicas de tipos para que la API reciba lo que espera
        try:
            router = int(data["router"]) if data.get("router") else None
        except (TypeError, ValueError):
            router = None

        try:
            subida = int(data["subida_mbps"]) if data.get("subida_mbps") else 0
            bajada = int(data["bajada_mbps"]) if data.get("bajada_mbps") else 0
        except (TypeError, ValueError):
            subida, bajada = 0, 0

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
        normalized["puerto_api"] = normalized.get("puerto_api") or 8729
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

        try:
            puerto_api = int(data.get("puerto_api", 8729)) if data.get("puerto_api") else 8729
        except (TypeError, ValueError):
            puerto_api = 8729

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

class FacturaFormMixin(APIViewMixin):
    estados = (
        ("pendiente", "Pendiente"),
        ("pagada", "Pagada"),
        ("vencida", "Vencida"),
        ("anulada", "Anulada"),
    )

    def get_clientes(self, api):
        clientes = api.get_list("clientes-pppoe/")
        normalized = []
        for cliente in clientes:
            item = dict(cliente)
            item["display_name"] = next(
                (
                    item[key]
                    for key in ("nombre_completo", "nombre", "usuario_pppoe")
                    if item.get(key) not in (None, "")
                ),
                f"Cliente #{item.get('id')}",
            )
            normalized.append(item)
        return normalized

    def normalize_factura_form_data(self, data):
        normalized = dict(data)
        normalized["cliente_id"] = _related_id(data.get("cliente"))
        return normalized

    def build_payload(self, data):
        try:
            cliente_id = int(data["cliente"]) if data.get("cliente") else None
        except (TypeError, ValueError):
            raise ValueError("Seleccione un cliente válido.") from None

        monto = _decimal(data.get("monto", 0))

        return {
            "cliente": cliente_id,
            "periodo": data.get("periodo"),
            "monto": f"{monto:.2f}",
            "fecha_vencimiento": data.get("fecha_vencimiento"),
            "estado": data.get("estado", "pendiente"),
            "observaciones": data.get("observaciones", "").strip(),
        }

class PagoFormMixin(APIViewMixin):
    metodos = (
        ("efectivo", "Efectivo"),
        ("transferencia", "Transferencia"),
        ("tarjeta", "Tarjeta"),
        ("otro", "Otro"),
    )

    def get_facturas(self, api):
        facturas = api.get_list("facturas/")
        normalized = []
        for factura in facturas:
            item = dict(factura)
            client_name = item.get("cliente_nombre")
            item["display_label"] = (
                f"Factura #{item.get('id')} - {client_name}"
                if client_name
                else f"Factura #{item.get('id')}"
            )
            normalized.append(item)
        return normalized

    def normalize_pago_form_data(self, data):
        normalized = dict(data)
        normalized["factura_id"] = _related_id(data.get("factura"))
        return normalized

    def build_payload(self, data):
        try:
            factura_id = int(data["factura"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Seleccione una factura válida.") from None

        try:
            monto = _decimal(data["monto"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Ingrese un monto válido.") from None
        if monto <= 0:
            raise ValueError("El monto debe ser mayor que cero.")

        metodo = data.get("metodo", "")
        if metodo not in {value for value, _label in self.metodos}:
            raise ValueError("Seleccione un método de pago válido.")

        referencia = data.get("referencia", "").strip()
        if len(referencia) > 100:
            raise ValueError("La referencia no puede superar 100 caracteres.")

        return {
            "factura": factura_id,
            "monto": f"{monto:.2f}",
            "metodo": metodo,
            "referencia": referencia,
        }
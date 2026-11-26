import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from ipaddress import ip_address

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from .api_client import APIError, MikrotikAPIClient, SesionCaducada
from .errores import MENSAJE_SESION_CADUCADA, mensaje_usuario
from .utils import _decimal, clear_api_session, _related_id, _related_form_id

logger = logging.getLogger(__name__)


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
        """Muestra el error de la API en español llano.

        El usuario solo ve el mensaje de `errores.mensaje_usuario()`: corto,
        en español y sin detalles internos (el detalle técnico ya quedó en
        el registro, logs/django.log, en el cliente de la API). Un error que
        no es de la API (un fallo propio de la web) sí se registra aquí con
        su traza, porque si no no quedaría en ningún sitio.

        Si la sesión caducó (401), limpia la sesión y levanta
        SesionCaducada: quien la recoge redirige a login con el mensaje de
        sesión caducada, en vez de dejar la página cargada con listas
        vacías y un mensaje críptico.
        """
        if getattr(exc, "status_code", None) == 401:
            clear_api_session(request)
            messages.error(request, MENSAJE_SESION_CADUCADA)
            raise SesionCaducada() from exc
        if not hasattr(exc, "status_code"):
            logger.exception("Error inesperado en la web: %s", exc)
        messages.error(request, mensaje_usuario(exc))


class AuthenticatedAPIViewMixin(APIViewMixin):
    def dispatch(self, request, *args, **kwargs):
        has_configured_token = bool(settings.MIKROTIK_API_TOKEN)
        has_configured_credentials = bool(
            settings.MIKROTIK_API_USERNAME and settings.MIKROTIK_API_PASSWORD
        )
        has_session_token = bool(request.session.get("mikrotik_api_token"))

        if not (has_configured_token or has_configured_credentials or has_session_token):
            messages.info(request, "Inicia sesión para continuar.")
            return redirect("login")
        try:
            return super().dispatch(request, *args, **kwargs)
        except SesionCaducada:
            # api_error() ya limpió la sesión y dejó el mensaje.
            return redirect("login")
        except APIError as exc:
            if getattr(exc, "status_code", None) == 401:
                # Un 401 que no pasó por api_error(): el mismo trato.
                clear_api_session(request)
                messages.error(request, MENSAJE_SESION_CADUCADA)
                return redirect("login")
            raise


class PlanFormMixin(APIViewMixin):
    @staticmethod
    def normalize_form_data(data):
        normalized = dict(data)
        normalized["router_id"] = _related_form_id(data.get("router"))
        return normalized

    @staticmethod
    def _catalogo_router(api, router_id, endpoint, clave):
        """Una lista de un catálogo del router (colas, direcciones, pools).

        Devuelve (items, error): items es la lista (vacía si la API no la
        trae) y error es el mensaje si la API falló (404/502, router sin
        respuesta...), o None si fue bien. Nunca levanta excepción: que un
        catálogo falle no debe romper el formulario. El mensaje de error es
        el de usuario (en español llano), nunca el texto crudo de la API:
        un 404 aquí casi siempre significa que el endpoint no existe en
        esa versión de la API, no que el router no tenga valores.
        """
        try:
            data = api.get(f"routers/{router_id}/{endpoint}/")
            items = data.get(clave) if isinstance(data, dict) else None
        except Exception as exc:
            if getattr(exc, "status_code", None) == 404:
                return [], "el endpoint no existe en esta versión de la API"
            return [], mensaje_usuario(exc)
        return items if isinstance(items, list) else [], None

    @staticmethod
    def _ids_routers(routers):
        ids = []
        for router in routers or []:
            router_id = _related_id(router.get("id")) if isinstance(router, dict) else router
            if router_id is not None:
                ids.append(router_id)
        return ids

    @staticmethod
    def get_colas_por_router(api, routers):
        """Colas simples por router para el desplegable de cola padre.

        Lee GET routers/{id}/colas/ de la API. Si la API no responde, el
        router no tiene colas o la API es anterior a ese endpoint, devuelve
        lista vacía para ese router: el formulario sigue funcionando y
        dejar la cola vacía es dejar el plan sin cola padre (la API ya no
        auto-genera Plan-{perfil}).
        """
        return PlanFormMixin.get_catalogos_plan(api, routers)[0]["colas"]

    @staticmethod
    def get_direcciones_por_router(api, routers):
        """Direcciones IP por router para el desplegable de direccion_local.

        Lee GET routers/{id}/direcciones-ip/ de la API (/ip/address). Cada
        entrada trae la interfaz y la IP sin máscara en "direccion": ese es
        el valor que se guarda en el plan (el perfil PPPoE pide una IP en
        local-address, no el nombre de la interfaz). Si el endpoint falla o
        no hay valores, devuelve lista vacía: el campo queda opcional.
        """
        return PlanFormMixin.get_catalogos_plan(api, routers)[0]["direcciones"]

    @staticmethod
    def get_pools_por_router(api, routers):
        """Pools por router para el desplegable de pool_remoto.

        Lee GET routers/{id}/pools/ de la API (/ip/pool). Se guarda el
        nombre del pool en el plan (remote-address del perfil PPPoE). Si el
        endpoint falla o no hay valores, devuelve lista vacía: el campo
        queda opcional.
        """
        return PlanFormMixin.get_catalogos_plan(api, routers)[0]["pools"]

    @staticmethod
    def get_catalogos_plan(api, routers):
        """Los tres catálogos del formulario de plan, con sus fallos.

        Devuelve (catalogos, fallos): catalogos es {"colas": {...},
        "direcciones": {...}, "pools": {...}} por router, y fallos es
        {str(router_id): {"colas": detalle, ...}} solo con los catálogos
        que fallaron, para avisar al usuario en vez de dejar desplegables
        vacíos en silencio. Un catálogo que falla nunca rompe el formulario.
        Cada catálogo se pide una sola vez por router.
        """
        catalogos = {"colas": {}, "direcciones": {}, "pools": {}}
        fallos = {}
        for router_id in PlanFormMixin._ids_routers(routers):
            clave = str(router_id)
            colas, error = PlanFormMixin._catalogo_router(api, router_id, "colas", "colas")
            catalogos["colas"][clave] = [
                {
                    "nombre": cola.get("nombre") or cola.get("name"),
                    "target": cola.get("target") or "",
                    "max_limit": cola.get("max-limit") or cola.get("max_limit") or "",
                    "parent": cola.get("parent") or "",
                }
                for cola in colas
                if isinstance(cola, dict) and (cola.get("nombre") or cola.get("name"))
            ]
            if error:
                fallos.setdefault(clave, {})["colas"] = error
            direcciones, error = PlanFormMixin._catalogo_router(
                api, router_id, "direcciones-ip", "direcciones"
            )
            catalogos["direcciones"][clave] = [
                {
                    "interfaz": item.get("interfaz") or item.get("interface") or "",
                    "direccion": item.get("direccion") or "",
                    "direccion_con_mascara": item.get("direccion_con_mascara") or "",
                    "red": item.get("red") or item.get("network") or "",
                }
                for item in direcciones
                if isinstance(item, dict) and item.get("direccion")
            ]
            if error:
                fallos.setdefault(clave, {})["direcciones IP"] = error
            pools, error = PlanFormMixin._catalogo_router(api, router_id, "pools", "pools")
            catalogos["pools"][clave] = [
                {
                    "nombre": item.get("nombre") or item.get("name"),
                    "rangos": item.get("rangos") or item.get("ranges") or "",
                }
                for item in pools
                if isinstance(item, dict) and (item.get("nombre") or item.get("name"))
            ]
            if error:
                fallos.setdefault(clave, {})["pools"] = error
        return catalogos, fallos

    @staticmethod
    def _velocidad(valor, campo):
        """Una velocidad en Mbps: entero mayor que 0, o error claro.

        Antes un valor no numérico se convertía en silencio en 0 Mbps y el
        plan se guardaba (o lo rechazaba la API con un error crudo): ahora
        el formulario dice qué corregir antes de enviar nada.
        """
        try:
            numero = int(valor)
        except (TypeError, ValueError):
            raise ValueError(
                f"Ingrese una velocidad de {campo} válida (un número entero)."
            ) from None
        if numero < 1:
            raise ValueError(f"La velocidad de {campo} debe ser mayor que 0 Mbps.")
        return numero

    def build_payload(self, data):
        # Limpieza básica de texto
        nombre = data.get("nombre_perfil", "").strip()
        cola_padre = data.get("cola_padre", "").strip()
        direccion_local = (data.get("direccion_local") or "").strip()
        pool_remoto = (data.get("pool_remoto") or "").strip()

        if not nombre:
            raise ValueError("Ingrese el nombre del perfil PPPoE.")
        if direccion_local:
            try:
                ip_address(direccion_local)
            except ValueError:
                raise ValueError("Ingrese una dirección IP local válida.") from None

        # Conversiones de tipos para que la API reciba lo que espera. Un
        # router no válido o una velocidad no numérica son errores del
        # formulario, no un None o un 0 silencioso para la API.
        try:
            router = int(data["router"]) if data.get("router") else None
        except (TypeError, ValueError):
            router = None
        if router is None:
            raise ValueError("Seleccione un router válido.")

        subida = self._velocidad(data.get("subida_mbps"), "subida")
        bajada = self._velocidad(data.get("bajada_mbps"), "descarga")

        return {
            "nombre_perfil": nombre,
            "cola_padre": cola_padre,
            # Vacía = sin cola padre: la API ya no auto-genera Plan-{perfil}.
            # direccion_local vacía = None: la API no toca el local-address
            # del perfil que ya existe en el router. El pool es texto:
            # vacío = "".
            "direccion_local": direccion_local or None,
            "pool_remoto": pool_remoto,
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

        # Un puerto no numérico antes se convertía en silencio en 8729:
        # ahora el formulario dice qué corregir.
        try:
            puerto_api = int(data.get("puerto_api", 8729)) if data.get("puerto_api") else 8729
        except (TypeError, ValueError):
            raise ValueError("Ingrese un puerto de API válido (un número entre 1 y 65535).") from None
        if not 1 <= puerto_api <= 65535:
            raise ValueError("Ingrese un puerto de API válido (un número entre 1 y 65535).")

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
            # Sin plan o router válidos el formulario explica qué falta, en
            # vez de romperse con un KeyError que la vista mostraba genérico.
            try:
                plan = int(data["plan"])
                router = int(data["router"])
            except (KeyError, TypeError, ValueError):
                raise ValueError("Seleccione un plan y un router válidos.") from None
            payload.update(
                plan=plan,
                router=router,
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

        # Un monto no numérico antes se convertía en silencio en 0.00 y la
        # factura se guardaba en 0: ahora el formulario dice qué corregir.
        crudo_monto = data.get("monto")
        if crudo_monto in (None, ""):
            raise ValueError("Ingrese un monto válido.") from None
        try:
            monto = Decimal(str(crudo_monto).replace(",", "."))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("Ingrese un monto válido.") from None

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
            monto = _decimal(data.get("monto"))
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

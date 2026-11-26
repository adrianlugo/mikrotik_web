from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import TemplateView, View
from ..errores import mensaje_usuario
from ..mixins import AuthenticatedAPIViewMixin
from ..utils import _pppoe_payload


def _nombres_routers_activos(active):
    """Nombres de router de GET clientes-pppoe/activos/.

    La API devuelve `routers` como lista de nombres (no `router` ni
    `router_nombre`): leer esas claves inexistentes mostraba "Desconocido"
    aunque hubiera datos. Se aceptan también dicts con nombre/name y las
    claves antiguas por compatibilidad.
    """
    routers = active.get("routers") if isinstance(active, dict) else None
    nombres = []
    if isinstance(routers, list):
        for router in routers:
            if isinstance(router, dict):
                nombre = router.get("nombre") or router.get("name") or router.get("ip_address")
            else:
                nombre = router
            if nombre:
                nombres.append(str(nombre))
    if not nombres and isinstance(active, dict):
        nombre = active.get("router_nombre") or active.get("router")
        if isinstance(nombre, dict):
            nombre = nombre.get("nombre") or nombre.get("name")
        if nombre:
            nombres.append(str(nombre))
    return nombres


def _resumen_activos(active):
    """Resumen honesto de las sesiones activas.

    total_conectados es el de la API, y si no viene se calcula con la
    lista de conexiones. `errores` es la lista de routers que la API no
    pudo consultar: con errores, el número puede estar incompleto.
    """
    conexiones = active.get("conexiones") or []
    total = active.get("total_conectados")
    if not isinstance(total, int):
        total = len(conexiones)
    errores = active.get("errores") or []
    return {
        "router_nombre": ", ".join(_nombres_routers_activos(active)),
        "routers_activos": _nombres_routers_activos(active),
        "total_conectados": total,
        "conexiones": conexiones,
        "activos_errores": errores if isinstance(errores, list) else [],
    }


class DashboardIndexView(AuthenticatedAPIViewMixin, TemplateView):
    template_name = "pppoe/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "planes": [],
                "routers": [],
                "conexiones": [],
                "total_conectados": None,
                # Los totales empiezan en None ("no se pudo consultar"), no
                # en 0: si una lista falla, la tarjeta muestra "—" en vez
                # de un 0 inventado.
                "total_clientes": None,
                "total_plan_count": None,
                "total_router_count": None,
                "planes_no_disponibles": False,
                "routers_no_disponibles": False,
                "clientes_no_disponibles": False,
                "router_nombre": "",
                "activos_errores": [],
                "activos_no_disponibles": False,
            }
        )
        api = self.api()
        try:
            active = api.get("clientes-pppoe/activos/")
            context.update(_resumen_activos(active))
        except Exception as exc:
            # La API falló (por ejemplo 502 con el router sin respuesta):
            # no se inventa un 0 de conectados. total_conectados queda en
            # None y la plantilla muestra "No disponible" y el error. Si la
            # sesión caducó (401), api_error() levanta SesionCaducada y el
            # dispatch redirige a login: no se sigue cargando el resto.
            context["activos_no_disponibles"] = True
            context["api_error"] = mensaje_usuario(exc)
            self.api_error(self.request, exc)

        fallos = {
            "planes": "planes_no_disponibles",
            "routers": "routers_no_disponibles",
            "clientes": "clientes_no_disponibles",
        }
        for key, path in (
            ("planes", "planes/"),
            ("routers", "routers/"),
            ("clientes", "clientes-pppoe/"),
        ):
            try:
                context[key] = api.get_list(path)
            except Exception as exc:
                context[key] = []
                context[fallos[key]] = True
                self.api_error(self.request, exc)
        context["planes"] = self.normalize_plans(context["planes"])
        context["routers"] = self.normalize_routers(context["routers"])
        # Total real de clientes PPPoE registrados en la API, no un 0 fijo.
        # Si la lista falló, queda en None ("no se pudo consultar").
        if not context["clientes_no_disponibles"]:
            context["total_clientes"] = len(context.get("clientes") or [])
        if not context["planes_no_disponibles"]:
            context["total_plan_count"] = len(context["planes"])
        if not context["routers_no_disponibles"]:
            context["total_router_count"] = len(context["routers"])
        return context

    def post(self, request, *args, **kwargs):
        try:
            router = int(request.POST["router"])
            plan = int(request.POST["plan"])
        except (KeyError, TypeError, ValueError):
            messages.error(request, "Seleccione un router y un plan válidos.")
            return redirect("dashboard_index")
        try:
            plans = self.api().get_list("planes/")
            payload = _pppoe_payload(request.POST, plans=plans)
            self.api().post("clientes-pppoe/", payload)
            messages.success(request, "Cliente PPPoE creado correctamente.")
        except ValueError as exc:
            messages.error(request, str(exc))
        except Exception as exc:
            self.api_error(request, exc)
        return redirect("dashboard_index")


class SincronizarMikrotikView(AuthenticatedAPIViewMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            router_id = int(request.POST["router"])
        except (KeyError, TypeError, ValueError):
            messages.error(request, "Seleccione el router que desea sincronizar.")
            return redirect("dashboard_index")

        try:
            self.api().post(f"routers/{router_id}/sincronizar/")
            messages.success(request, "Sincronización con MikroTik completada.")
        except Exception as exc:
            self.api_error(request, exc)
        return redirect("dashboard_index")

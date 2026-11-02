from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import TemplateView, View

from .api_client import APIError, MikrotikAPIClient


class APIViewMixin:
    def api(self):
        return MikrotikAPIClient()

    def api_error(self, request, exc):
        messages.error(request, str(exc))


class DashboardIndexView(APIViewMixin, TemplateView):
    template_name = "pppoe/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"planes": [], "routers": [], "conexiones": [], "total_conectados": 0})
        api = self.api()
        try:
            active = api.get("clientes-pppoe/activos/")
            context["router_nombre"] = active.get("router") or active.get("router_nombre") or "Desconocido"
            context["total_conectados"] = active.get("total_conectados", 0)
            context["conexiones"] = active.get("conexiones", [])
        except APIError as exc:
            context["api_error"] = str(exc)

        for key, path in (("planes", "planes/"), ("routers", "routers/")):
            try:
                context[key] = api.get_list(path)
            except APIError:
                context[key] = []
        context["total_clientes"] = context.get("total_clientes", 0)
        context["total_plan_count"] = len(context["planes"])
        context["total_router_count"] = len(context["routers"])
        return context

    def post(self, request, *args, **kwargs):
        try:
            router = int(request.POST["router"])
            plan = int(request.POST["plan"])
        except (KeyError, TypeError, ValueError):
            messages.error(request, "Seleccione un router y un plan válidos.")
            return redirect("dashboard_index")

        payload = {
            "usuario_pppoe": request.POST.get("usuario"),
            "password_pppoe": request.POST.get("password"),
            "nombre_completo": request.POST.get("nombre_completo"),
            "plan": plan,
            "router": router,
            "estado": "activo",
        }
        try:
            self.api().post("clientes-pppoe/", payload)
            messages.success(request, "Cliente PPPoE creado correctamente.")
        except APIError as exc:
            self.api_error(request, exc)
        return redirect("dashboard_index")


class SincronizarMikrotikView(APIViewMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            self.api().post("clientes-pppoe/importar-desde-mikrotik/")
            messages.success(request, "Sincronización con MikroTik completada.")
        except APIError as exc:
            self.api_error(request, exc)
        return redirect("dashboard_index")


class ClientesListView(APIViewMixin, TemplateView):
    template_name = "pppoe/clientes.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["clientes"] = self.api().get_list("clientes-pppoe/")
        except APIError as exc:
            context.update(clientes=[], api_error=str(exc))
        return context


class PlanesListView(APIViewMixin, TemplateView):
    template_name = "pppoe/planes.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["planes"] = self.api().get_list("planes/")
        except APIError as exc:
            context.update(planes=[], api_error=str(exc))
        return context


class ConexionActivaView(APIViewMixin, TemplateView):
    template_name = "pppoe/conexiones.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            active = self.api().get("clientes-pppoe/activos/")
            context.update(
                conexiones=active.get("conexiones", []),
                total_conectados=active.get("total_conectados", 0),
                router_nombre=active.get("router") or active.get("router_nombre") or "Desconocido",
            )
        except APIError as exc:
            context.update(conexiones=[], total_conectados=0, api_error=str(exc))
        return context


class ClienteEstadoView(APIViewMixin, View):
    def post(self, request, pk, *args, **kwargs):
        try:
            self.api().post(f"clientes-pppoe/{pk}/cambiar-estado/")
            messages.success(request, "Estado del cliente actualizado.")
        except APIError as exc:
            self.api_error(request, exc)
        return redirect("clientes_list")


class RoutersListView(APIViewMixin, TemplateView):
    template_name = "network/routers.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["routers"] = self.api().get_list("routers/")
        except APIError as exc:
            context.update(routers=[], api_error=str(exc))
        return context


class EnlacesISPListView(APIViewMixin, TemplateView):
    template_name = "network/enlaces.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["enlaces"] = self.api().get_list("enlaces-isp/")
        except APIError as exc:
            context.update(enlaces=[], api_error=str(exc))
        return context


class InterfacesListView(APIViewMixin, TemplateView):
    template_name = "network/interfaces.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["interfaces"] = self.api().get_list("interfaces/")
        except APIError as exc:
            context.update(interfaces=[], api_error=str(exc))
        return context


class ClienteEliminarView(APIViewMixin, View):
    def post(self, request, pk, *args, **kwargs):
        try:
            self.api().delete(f"clientes-pppoe/{pk}/")
            messages.success(request, "Cliente eliminado correctamente.")
        except APIError as exc:
            self.api_error(request, exc)
        return redirect("clientes_list")

from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import TemplateView, View
from ..mixins import AuthenticatedAPIViewMixin
from ..utils import _pppoe_payload


class DashboardIndexView(AuthenticatedAPIViewMixin, TemplateView):
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
        except Exception as exc:
            context["api_error"] = str(exc)
            self.api_error(self.request, exc)
            if getattr(exc, "status_code", None) == 401:
                return context

        for key, path in (("planes", "planes/"), ("routers", "routers/")):
            try:
                context[key] = api.get_list(path)
            except Exception as exc:
                context[key] = []
                self.api_error(self.request, exc)
                if getattr(exc, "status_code", None) == 401:
                    break
        context["planes"] = self.normalize_plans(context["planes"])
        context["routers"] = self.normalize_routers(context["routers"])
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
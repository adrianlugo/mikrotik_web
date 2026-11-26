from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import TemplateView, View
from ..mixins import AuthenticatedAPIViewMixin, RouterFormMixin


class RoutersListView(AuthenticatedAPIViewMixin, TemplateView):
    template_name = "network/routers.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["routers"] = self.normalize_routers(self.api().get_list("routers/"))
        except Exception as exc:
            context.update(routers=[], api_error=str(exc))
            self.api_error(self.request, exc)
        return context


class RouterCrearView(RouterFormMixin, AuthenticatedAPIViewMixin, TemplateView):
    template_name = "network/router_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            form_action="crear",
            form_data={"activo_checked": True, "puerto_api": 8729},
        )
        return context

    def post(self, request, *args, **kwargs):
        try:
            payload = self.build_payload(request.POST)
        except ValueError as exc:
            messages.error(request, str(exc))
            context = self.get_context_data()
            context.update(form_data=self.normalize_form_data(request.POST.dict()))
            return self.render_to_response(context)

        try:
            self.api().post("routers/", payload)
            messages.success(request, "Router registrado correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
            context = self.get_context_data()
            context.update(api_error=str(exc), form_data=self.normalize_form_data(request.POST.dict()))
            return self.render_to_response(context)
        return redirect("routers_list")


class RouterEditarView(RouterFormMixin, AuthenticatedAPIViewMixin, TemplateView):
    template_name = "network/router_form.html"

    def get_context_data(self, router_id, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(form_action="editar", router_id=router_id)
        try:
            data = self.api().get(f"routers/{router_id}/")
            context["form_data"] = self.normalize_form_data(data)
        except Exception as exc:
            context.update(form_data={}, api_error=str(exc))
            self.api_error(self.request, exc)
        return context

    def post(self, request, router_id, *args, **kwargs):
        try:
            payload = self.build_payload(request.POST, partial=True)
        except ValueError as exc:
            messages.error(request, str(exc))
            context = self.get_context_data(router_id=router_id)
            context.update(form_data=self.normalize_form_data(request.POST.dict()))
            return self.render_to_response(context)

        try:
            self.api().patch(f"routers/{router_id}/", payload)
            messages.success(request, "Router actualizado correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
            context = self.get_context_data(router_id=router_id)
            context.update(api_error=str(exc), form_data=self.normalize_form_data(request.POST.dict()))
            return self.render_to_response(context)
        return redirect("router_detalle", router_id=router_id)


class RouterDetalleView(AuthenticatedAPIViewMixin, TemplateView):
    template_name = "network/router_detalle.html"

    def get_context_data(self, router_id, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(router_id=router_id, router={}, estado={}, api_error=None)
        api = self.api()
        try:
            router = api.get(f"routers/{router_id}/")
            context["router"] = self._normalize_router(router)
        except Exception as exc:
            context["api_error"] = str(exc)
            self.api_error(self.request, exc)
            return context

        try:
            estado = api.get(f"routers/{router_id}/estado/")
            context["estado"] = estado if isinstance(estado, dict) else {}
        except Exception as exc:
            context["api_error"] = str(exc)
            self.api_error(self.request, exc)
        return context


class RouterEliminarView(AuthenticatedAPIViewMixin, View):
    def post(self, request, router_id, *args, **kwargs):
        try:
            self.api().delete(f"routers/{router_id}/")
            messages.success(request, "Router eliminado correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
        return redirect("routers_list")


class RouterAccionView(AuthenticatedAPIViewMixin, View):
    accion = None
    mensaje_exito = ""

    def post(self, request, router_id, *args, **kwargs):
        try:
            response = self.api().post(f"routers/{router_id}/{self.accion}/")
            if isinstance(response, dict) and response.get("status") == "error":
                messages.error(request, response.get("message", "La operación del router falló."))
            else:
                detail = response.get("detail") if isinstance(response, dict) else None
                messages.success(request, detail or self.mensaje_exito)
        except Exception as exc:
            self.api_error(request, exc)
        return redirect("router_detalle", router_id=router_id)


class RouterVerificarView(RouterAccionView):
    accion = "verificar-conexion"
    mensaje_exito = "Conexión con RouterOS verificada."


class RouterSincronizarView(RouterAccionView):
    accion = "sincronizar"
    mensaje_exito = "Sincronización manual completada."


class RouterRepararColasView(RouterAccionView):
    accion = "reparar-colas"
    mensaje_exito = "Colas DHCP/IP fija reparadas."


class RouterConsumoView(AuthenticatedAPIViewMixin, TemplateView):
    template_name = "network/router_monitoreo.html"

    def get_context_data(self, router_id, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(router_id=router_id, router={}, consumo=[], total=0, tipo="consumo", consulta_fallida=False)
        api = self.api()
        try:
            context["router"] = self._normalize_router(api.get(f"routers/{router_id}/"))
            consumo = api.get(f"routers/{router_id}/consumo/")
            colas = consumo.get("colas", []) if isinstance(consumo, dict) else []
            context["consumo"] = [
                {
                    **cola,
                    "max_limit": cola.get("max-limit", cola.get("max_limit")),
                }
                for cola in colas
            ]
            context["total"] = consumo.get("total_colas", len(context["consumo"])) if isinstance(consumo, dict) else 0
        except Exception as exc:
            # Sin inventar una lista vacía: la plantilla distingue "no hay
            # colas" de "no se pudo consultar el router".
            context["consulta_fallida"] = True
            context["api_error"] = str(exc)
            self.api_error(self.request, exc)
        return context


class RouterLeasesView(AuthenticatedAPIViewMixin, TemplateView):
    template_name = "network/router_monitoreo.html"

    def get_context_data(self, router_id, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(router_id=router_id, router={}, leases=[], total=0, tipo="leases", consulta_fallida=False)
        api = self.api()
        try:
            context["router"] = self._normalize_router(api.get(f"routers/{router_id}/"))
            leases = api.get(f"routers/{router_id}/dhcp-leases/")
            leases_data = leases.get("leases", []) if isinstance(leases, dict) else []
            context["leases"] = [
                {
                    **lease,
                    "mac_address": lease.get("mac-address", lease.get("mac_address")),
                    "server": lease.get("server", lease.get("dhcp_server")),
                }
                for lease in leases_data
            ]
            context["total"] = leases.get("total", len(context["leases"])) if isinstance(leases, dict) else 0
        except Exception as exc:
            context["consulta_fallida"] = True
            context["api_error"] = str(exc)
            self.api_error(self.request, exc)
        return context
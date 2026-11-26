from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import TemplateView, View
from ..mixins import AuthenticatedAPIViewMixin, PlanFormMixin
from ..utils import _related_id, _pppoe_payload


class ClientesListView(AuthenticatedAPIViewMixin, TemplateView):
    template_name = "pppoe/clientes.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["clientes"] = self.api().get_list("clientes-pppoe/")
        except Exception as exc:
            context.update(clientes=[], api_error=str(exc))
            self.api_error(self.request, exc)
        return context


class ClienteCrearView(AuthenticatedAPIViewMixin, TemplateView):
    template_name = "pppoe/cliente_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        api = self.api()
        try:
            context["routers"] = self.normalize_routers(api.get_list("routers/"))
            context["planes"] = self.normalize_plans(api.get_list("planes/"))
        except Exception as exc:
            context.update(routers=[], planes=[], api_error=str(exc))
            self.api_error(self.request, exc)
        context["form_data"] = kwargs.get("form_data", {})
        if kwargs.get("api_error"):
            context["api_error"] = kwargs["api_error"]
        return context

    def post(self, request, *args, **kwargs):
        api = self.api()
        try:
            plans = self.normalize_plans(api.get_list("planes/"))
        except Exception as exc:
            self.api_error(request, exc)
            return self.render_to_response(
                self.get_context_data(form_data=request.POST, api_error=str(exc)),
                status=400,
            )

        try:
            payload = _pppoe_payload(request.POST, plans=plans)
        except ValueError as exc:
            messages.error(request, str(exc))
            return self.render_to_response(
                self.get_context_data(form_data=request.POST),
                status=400,
            )

        try:
            api.post("clientes-pppoe/", payload)
            messages.success(request, "Cliente PPPoE creado correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
            return self.render_to_response(
                self.get_context_data(form_data=request.POST, api_error=str(exc)),
                status=400,
            )
        return redirect("clientes_list")


class PlanesListView(AuthenticatedAPIViewMixin, TemplateView):
    template_name = "pppoe/planes.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            api = self.api()
            planes = api.get_list("planes/")
            routers = self.normalize_routers(api.get_list("routers/"))
        except Exception as exc:
            context.update(planes=[], api_error=str(exc))
            self.api_error(self.request, exc)
            return context

        router_names = {
            str(router.get("id")): router.get("nombre")
            or router.get("name")
            or router.get("ip_address")
            for router in routers
        }
        normalized_planes = self.normalize_plans(planes)
        for plan in normalized_planes:
            router_id = _related_id(plan.get("router"))
            plan["router_nombre"] = router_names.get(str(router_id), "")
        context["planes"] = normalized_planes
        return context


class PlanCrearView(PlanFormMixin, AuthenticatedAPIViewMixin, TemplateView):
    template_name = "pppoe/plan_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(form_action="crear", form_data={"router_id": None})
        try:
            api = self.api()
            context["routers"] = self.normalize_routers(api.get_list("routers/"))
            context["colas_por_router"] = self.get_colas_por_router(api, context["routers"])
        except Exception as exc:
            context["routers"] = []
            context["colas_por_router"] = {}
            context["api_error"] = str(exc)
            self.api_error(self.request, exc)
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
            self.api().post("planes/", payload)
            messages.success(request, "Plan creado correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
            context = self.get_context_data()
            context.update(api_error=str(exc), form_data=self.normalize_form_data(request.POST.dict()))
            return self.render_to_response(context)
        return redirect("planes_list")


class PlanEditarView(PlanFormMixin, AuthenticatedAPIViewMixin, TemplateView):
    template_name = "pppoe/plan_form.html"

    def get_context_data(self, plan_id, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(form_action="editar", plan_id=plan_id)
        api = self.api()
        try:
            plan = api.get(f"planes/{plan_id}/")
            context["form_data"] = self.normalize_form_data(plan)
            context["routers"] = self.normalize_routers(api.get_list("routers/"))
            context["colas_por_router"] = self.get_colas_por_router(api, context["routers"])
        except Exception as exc:
            context.update(form_data={}, routers=[], colas_por_router={}, api_error=str(exc))
            self.api_error(self.request, exc)
        return context

    def post(self, request, plan_id, *args, **kwargs):
        try:
            payload = self.build_payload(request.POST)
        except ValueError as exc:
            messages.error(request, str(exc))
            context = self.get_context_data(plan_id=plan_id)
            context.update(form_data=self.normalize_form_data(request.POST.dict()))
            return self.render_to_response(context)

        try:
            self.api().patch(f"planes/{plan_id}/", payload)
            messages.success(request, "Plan actualizado correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
            context = self.get_context_data(plan_id=plan_id)
            context.update(api_error=str(exc), form_data=self.normalize_form_data(request.POST.dict()))
            return self.render_to_response(context)
        return redirect("planes_list")


class PlanEliminarView(AuthenticatedAPIViewMixin, View):
    def post(self, request, plan_id, *args, **kwargs):
        try:
            self.api().delete(f"planes/{plan_id}/")
            messages.success(request, "Plan eliminado correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
        return redirect("planes_list")


class ConexionActivaView(AuthenticatedAPIViewMixin, TemplateView):
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
        except Exception as exc:
            context.update(conexiones=[], total_conectados=0, api_error=str(exc))
            self.api_error(self.request, exc)
        return context


class ClienteEstadoView(AuthenticatedAPIViewMixin, View):
    def post(self, request, pk, *args, **kwargs):
        try:
            cliente = self.api().get(f"clientes-pppoe/{pk}/")
            nuevo_estado = "activo" if cliente.get("estado") != "activo" else "suspendido"
            response = self.api().post(
                f"clientes-pppoe/{pk}/cambiar-estado/",
                {"estado": nuevo_estado},
            )
            detail = response.get("message") if isinstance(response, dict) else None
            messages.success(request, detail or "Estado del cliente actualizado.")
        except Exception as exc:
            self.api_error(request, exc)
        return redirect("clientes_list")


class ClienteEditarView(AuthenticatedAPIViewMixin, TemplateView):
    template_name = "pppoe/cliente_editar.html"

    def get_context_data(self, pk, **kwargs):
        context = super().get_context_data(**kwargs)
        api = self.api()
        context["cliente_id"] = pk

        try:
            context["cliente"] = api.get(f"clientes-pppoe/{pk}/")
            context["cliente_plan_id"] = _related_id(context["cliente"].get("plan"))
            context["cliente_router_id"] = _related_id(context["cliente"].get("router"))
            context["planes"] = self.normalize_plans(api.get_list("planes/"))
            context["routers"] = self.normalize_routers(api.get_list("routers/"))
        except Exception as exc:
            context.update(cliente=None, planes=[], routers=[], api_error=str(exc))
            self.api_error(self.request, exc)
        return context

    def post(self, request, pk, *args, **kwargs):
        try:
            planes = self.normalize_plans(self.api().get_list("planes/"))
            payload = _pppoe_payload(request.POST, plans=planes, require_password=False)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("cliente_editar", pk=pk)
        except Exception as exc:
            self.api_error(request, exc)
            return redirect("cliente_editar", pk=pk)

        password = request.POST.get("password_pppoe", "").strip()
        if password:
            payload["password_pppoe"] = password
        else:
            payload.pop("password_pppoe", None)

        try:
            self.api().patch(f"clientes-pppoe/{pk}/", payload)
            messages.success(request, "Cliente PPPoE actualizado correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
        return redirect("clientes_list")


class ClientePingView(AuthenticatedAPIViewMixin, View):
    def post(self, request, pk, *args, **kwargs):
        try:
            response = self.api().post(f"clientes-pppoe/{pk}/ping/")
            detail = response.get("detail") if isinstance(response, dict) else None
            messages.success(request, detail or "Prueba de conexión enviada al cliente PPPoE.")
        except Exception as exc:
            self.api_error(request, exc)
        return redirect("clientes_list")


class ClientePatearView(AuthenticatedAPIViewMixin, View):
    def post(self, request, pk, *args, **kwargs):
        try:
            response = self.api().post(f"clientes-pppoe/{pk}/patear/")
            detail = response.get("detail") if isinstance(response, dict) else None
            messages.success(request, detail or "Sesión PPPoE desconectada correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
        return redirect("clientes_list")


class ClienteEliminarView(AuthenticatedAPIViewMixin, View):
    def post(self, request, pk, *args, **kwargs):
        try:
            self.api().delete(f"clientes-pppoe/{pk}/")
            messages.success(request, "Cliente eliminado correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
        return redirect("clientes_list")
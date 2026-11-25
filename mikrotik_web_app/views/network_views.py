from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import TemplateView, View
from ..mixins import AuthenticatedAPIViewMixin, ClienteRedFormMixin


class ClientesRedListView(AuthenticatedAPIViewMixin, TemplateView):
    template_name = "network/clientes_red.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["clientes"] = self.api().get_list("clientes-red/")
        except Exception as exc:
            context.update(clientes=[], api_error=str(exc))
            self.api_error(self.request, exc)
        return context


class ClienteRedCrearView(ClienteRedFormMixin, AuthenticatedAPIViewMixin, TemplateView):
    template_name = "network/cliente_red_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(form_action="crear", cliente={}, form_data={})
        try:
            context.update(self.get_catalogs(self.api()))
        except Exception as exc:
            context.update(planes=[], routers=[], api_error=str(exc))
            self.api_error(self.request, exc)
        return context

    def post(self, request, *args, **kwargs):
        try:
            payload = self.build_payload(request.POST)
        except (KeyError, TypeError, ValueError):
            messages.error(request, "Seleccione un plan y un router válidos.")
            return redirect("cliente_red_crear")

        try:
            self.api().post("clientes-red/", payload)
            messages.success(request, "Cliente DHCP/IP fija creado correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
            context = self.get_context_data()
            form_data = self.normalize_form_data(request.POST.dict())
            context.update(api_error=str(exc), form_data=form_data, cliente=form_data)
            return self.render_to_response(context)
        return redirect("clientes_red_list")


class ClienteRedEditarView(ClienteRedFormMixin, AuthenticatedAPIViewMixin, TemplateView):
    template_name = "network/cliente_red_form.html"

    def get_context_data(self, pk, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_action"] = "editar"
        context["cliente_id"] = pk
        api = self.api()
        try:
            context["cliente"] = api.get(f"clientes-red/{pk}/")
            context["form_data"] = self.normalize_form_data(context["cliente"])
            context.update(self.get_catalogs(api))
        except Exception as exc:
            context.update(cliente={}, form_data={}, planes=[], routers=[], api_error=str(exc))
            self.api_error(self.request, exc)
        return context

    def post(self, request, pk, *args, **kwargs):
        try:
            payload = self.build_payload(request.POST)
        except (KeyError, TypeError, ValueError):
            messages.error(request, "Seleccione un plan y un router válidos.")
            return redirect("cliente_red_editar", pk=pk)

        try:
            self.api().patch(f"clientes-red/{pk}/", payload)
            messages.success(request, "Cliente DHCP/IP fija actualizado correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
            context = self.get_context_data(pk=pk)
            form_data = self.normalize_form_data(request.POST.dict())
            context.update(api_error=str(exc), form_data=form_data, cliente=form_data)
            return self.render_to_response(context)
        return redirect("clientes_red_list")


class ClienteRedRepararColaView(AuthenticatedAPIViewMixin, View):
    def post(self, request, pk, *args, **kwargs):
        try:
            self.api().post(f"clientes-red/{pk}/crear-cola/")
            messages.success(request, "Reserva y cola del cliente reparadas correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
        return redirect("clientes_red_list")


class ClienteRedEliminarView(AuthenticatedAPIViewMixin, View):
    def post(self, request, pk, *args, **kwargs):
        try:
            self.api().delete(f"clientes-red/{pk}/")
            messages.success(request, "Cliente DHCP/IP fija eliminado correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
        return redirect("clientes_red_list")

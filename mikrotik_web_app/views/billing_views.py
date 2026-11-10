from datetime import date
from decimal import Decimal
from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import TemplateView, View
from ..mixins import AuthenticatedAPIViewMixin, APIViewMixin
from ..utils import _decimal, _related_id, _related_form_id


class FacturaListView(AuthenticatedAPIViewMixin, TemplateView):
    template_name = "billing/facturas.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        api = self.api()
        facturas = []
        pagos = []
        api_errors = []

        try:
            facturas = api.get_list("facturas/")
        except Exception as exc:
            api_errors.append(str(exc))
            self.api_error(self.request, exc)

        try:
            pagos = api.get_list("pagos/")
        except Exception as exc:
            api_errors.append(str(exc))
            self.api_error(self.request, exc)

        paid_by_invoice = {}
        for pago in pagos:
            invoice_id = _related_id(pago.get("factura"))
            if invoice_id is None:
                continue
            paid_by_invoice[invoice_id] = paid_by_invoice.get(
                invoice_id, Decimal("0")
            ) + _decimal(pago.get("monto"))

        normalized_facturas = []
        for factura in facturas:
            normalized = dict(factura)
            invoice_id = normalized.get("id")
            amount = _decimal(normalized.get("monto"))
            paid = paid_by_invoice.get(invoice_id, Decimal("0"))
            balance = amount - paid
            if balance < 0:
                balance = Decimal("0")
            normalized["cliente_id"] = _related_id(normalized.get("cliente"))
            normalized["cliente_nombre"] = normalized.get("cliente_nombre") or next(
                (
                    normalized[key]
                    for key in ("cliente_nombre_completo", "cliente_display")
                    if normalized.get(key) not in (None, "")
                ),
                (
                    normalized["cliente"].get("nombre_completo")
                    if isinstance(normalized.get("cliente"), dict)
                    else f"Cliente #{normalized['cliente_id']}"
                ),
            )
            normalized["monto_mostrado"] = f"{amount:.2f}"
            normalized["pagado_mostrado"] = f"{paid:.2f}"
            normalized["saldo_mostrado"] = f"{balance:.2f}"
            normalized_facturas.append(normalized)

        context["facturas"] = normalized_facturas
        if api_errors:
            context["api_error"] = " ".join(api_errors)
        return context


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
            cliente_id = int(data["cliente"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Seleccione un cliente PPPoE válido.") from None

        try:
            monto = _decimal(data["monto"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Ingrese un monto válido.") from None
        if monto <= 0:
            raise ValueError("El monto debe ser mayor que cero.")

        try:
            periodo = date.fromisoformat(data["periodo"])
            periodo = periodo.replace(day=1)
        except (KeyError, TypeError, ValueError):
            raise ValueError("Ingrese un período válido.") from None

        try:
            fecha_vencimiento = date.fromisoformat(data["fecha_vencimiento"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Ingrese una fecha de vencimiento válida.") from None

        estado = data.get("estado", "pendiente")
        if estado not in {value for value, _label in self.estados}:
            raise ValueError("Seleccione un estado válido.")

        return {
            "cliente": cliente_id,
            "periodo": periodo.isoformat(),
            "monto": f"{monto:.2f}",
            "fecha_vencimiento": fecha_vencimiento.isoformat(),
            "estado": estado,
            "observaciones": data.get("observaciones", "").strip(),
        }


class FacturaCrearView(FacturaFormMixin, AuthenticatedAPIViewMixin, TemplateView):
    template_name = "billing/factura_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(form_action="crear", form_data={}, estados=self.estados)
        try:
            context["clientes"] = self.get_clientes(self.api())
        except Exception as exc:
            context["clientes"] = []
            context["api_error"] = str(exc)
            self.api_error(self.request, exc)
        return context

    def post(self, request, *args, **kwargs):
        try:
            payload = self.build_payload(request.POST)
        except ValueError as exc:
            messages.error(request, str(exc))
            context = self.get_context_data()
            context["form_data"] = request.POST.dict()
            context["cliente_id"] = _related_form_id(request.POST.get("cliente"))
            return self.render_to_response(context)

        try:
            self.api().post("facturas/", payload)
            messages.success(request, "Factura creada correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
            context = self.get_context_data()
            context.update(
                api_error=str(exc),
                form_data=request.POST.dict(),
                cliente_id=_related_form_id(request.POST.get("cliente")),
            )
            return self.render_to_response(context)
        return redirect("facturas_list")


class FacturaEditarView(FacturaFormMixin, AuthenticatedAPIViewMixin, TemplateView):
    template_name = "billing/factura_form.html"

    def get_context_data(self, pk, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(form_action="editar", factura_id=pk, estados=self.estados)
        api = self.api()
        try:
            factura = api.get(f"facturas/{pk}/")
            context["factura"] = factura
            context["form_data"] = self.normalize_factura_form_data(factura)
            context["clientes"] = self.get_clientes(api)
        except Exception as exc:
            context.update(factura={}, form_data={}, clientes=[], api_error=str(exc))
            self.api_error(self.request, exc)
        return context

    def post(self, request, pk, *args, **kwargs):
        try:
            payload = self.build_payload(request.POST)
        except ValueError as exc:
            messages.error(request, str(exc))
            context = self.get_context_data(pk=pk)
            context["form_data"] = request.POST.dict()
            context["cliente_id"] = _related_form_id(request.POST.get("cliente"))
            return self.render_to_response(context)

        try:
            self.api().patch(f"facturas/{pk}/", payload)
            messages.success(request, "Factura actualizada correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
            context = self.get_context_data(pk=pk)
            context.update(
                api_error=str(exc),
                form_data=request.POST.dict(),
                cliente_id=_related_form_id(request.POST.get("cliente")),
            )
            return self.render_to_response(context)
        return redirect("facturas_list")


class FacturaEliminarView(AuthenticatedAPIViewMixin, View):
    def post(self, request, pk, *args, **kwargs):
        try:
            self.api().delete(f"facturas/{pk}/")
            messages.success(request, "Factura eliminada correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
        return redirect("facturas_list")


class PagoListView(AuthenticatedAPIViewMixin, TemplateView):
    template_name = "billing/pagos.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        api = self.api()
        pagos = []
        facturas = []
        api_errors = []

        try:
            pagos = api.get_list("pagos/")
        except Exception as exc:
            api_errors.append(str(exc))
            self.api_error(self.request, exc)

        try:
            facturas = api.get_list("facturas/")
        except Exception as exc:
            api_errors.append(str(exc))
            self.api_error(self.request, exc)

        factura_labels = {}
        for factura in facturas:
            invoice_id = factura.get("id")
            client_name = factura.get("cliente_nombre")
            factura_labels[invoice_id] = (
                f"Factura #{invoice_id} - {client_name}"
                if client_name
                else f"Factura #{invoice_id}"
            )

        normalized_pagos = []
        for pago in pagos:
            normalized = dict(pago)
            invoice_id = _related_id(normalized.get("factura"))
            normalized["factura_id"] = invoice_id
            normalized["factura_label"] = factura_labels.get(
                invoice_id, f"Factura #{invoice_id}"
            )
            normalized["monto_mostrado"] = f"{_decimal(normalized.get('monto')):.2f}"
            normalized_pagos.append(normalized)

        context["pagos"] = normalized_pagos
        if api_errors:
            context["api_error"] = " ".join(api_errors)
        return context


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


class PagoCrearView(PagoFormMixin, AuthenticatedAPIViewMixin, TemplateView):
    template_name = "billing/pago_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            form_action="crear",
            form_data={
                "factura": self.request.GET.get("factura", ""),
                "metodo": "efectivo",
            },
            metodos=self.metodos,
            factura_id=_related_form_id(self.request.GET.get("factura")),
        )
        try:
            context["facturas"] = self.get_facturas(self.api())
        except Exception as exc:
            context["facturas"] = []
            context["api_error"] = str(exc)
            self.api_error(self.request, exc)
        return context

    def post(self, request, *args, **kwargs):
        try:
            payload = self.build_payload(request.POST)
        except ValueError as exc:
            messages.error(request, str(exc))
            context = self.get_context_data()
            context["form_data"] = request.POST.dict()
            context["factura_id"] = _related_form_id(request.POST.get("factura"))
            return self.render_to_response(context)

        try:
            self.api().post("pagos/", payload)
            messages.success(request, "Pago registrado correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
            context = self.get_context_data()
            context.update(
                api_error=str(exc),
                form_data=request.POST.dict(),
                factura_id=_related_form_id(request.POST.get("factura")),
            )
            return self.render_to_response(context)
        return redirect("pagos_list")


class PagoEditarView(PagoFormMixin, AuthenticatedAPIViewMixin, TemplateView):
    template_name = "billing/pago_form.html"

    def get_context_data(self, pk, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(form_action="editar", pago_id=pk, metodos=self.metodos)
        api = self.api()
        try:
            pago = api.get(f"pagos/{pk}/")
            context["pago"] = pago
            context["form_data"] = self.normalize_pago_form_data(pago)
            context["facturas"] = self.get_facturas(api)
        except Exception as exc:
            context.update(pago={}, form_data={}, facturas=[], api_error=str(exc))
            self.api_error(self.request, exc)
        return context

    def post(self, request, pk, *args, **kwargs):
        try:
            payload = self.build_payload(request.POST)
        except ValueError as exc:
            messages.error(request, str(exc))
            context = self.get_context_data(pk=pk)
            context["form_data"] = request.POST.dict()
            context["factura_id"] = _related_form_id(request.POST.get("factura"))
            return self.render_to_response(context)

        try:
            self.api().patch(f"pagos/{pk}/", payload)
            messages.success(request, "Pago actualizado correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
            context = self.get_context_data(pk=pk)
            context.update(
                api_error=str(exc),
                form_data=request.POST.dict(),
                factura_id=_related_form_id(request.POST.get("factura")),
            )
            return self.render_to_response(context)
        return redirect("pagos_list")


class PagoEliminarView(AuthenticatedAPIViewMixin, View):
    def post(self, request, pk, *args, **kwargs):
        try:
            self.api().delete(f"pagos/{pk}/")
            messages.success(request, "Pago eliminado correctamente.")
        except Exception as exc:
            self.api_error(request, exc)
        return redirect("pagos_list")
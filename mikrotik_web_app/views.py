from ipaddress import ip_address
import re

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import TemplateView, View

from .api_client import APIError, MikrotikAPIClient


def _related_id(value):
    if isinstance(value, dict):
        return value.get("id") or value.get("pk")
    return value


def _related_form_id(value):
    try:
        return int(_related_id(value))
    except (TypeError, ValueError):
        return None


def _pppoe_form_value(data, primary, fallback):
    value = data.get(primary)
    if value in (None, "") and fallback:
        value = data.get(fallback)
    return value or ""


def _pppoe_payload(data, plans=None, require_password=True):
    nombre = str(data.get("nombre_completo", "")).strip()
    usuario = str(_pppoe_form_value(data, "usuario_pppoe", "usuario")).strip().lower()
    password = str(_pppoe_form_value(data, "password_pppoe", "password")).strip()
    ip_antena = str(data.get("direccion_ip_antena", "")).strip()

    if not nombre:
        raise ValueError("Ingrese el nombre completo del cliente.")
    if not re.fullmatch(r"[a-z0-9._-]+", usuario):
        raise ValueError(
            "El usuario PPPoE solo puede contener letras minúsculas, números, puntos, guiones y guiones bajos."
        )
    if (require_password and not password) or (password and len(password) < 6):
        raise ValueError("La contraseña PPPoE debe tener al menos 6 caracteres.")
    if ip_antena:
        try:
            ip_address(ip_antena)
        except ValueError:
            raise ValueError("Ingrese una dirección IP de antena válida.") from None

    try:
        router = int(data["router"])
        plan = int(data["plan"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("Seleccione un router y un plan válidos.") from None

    if plans is not None:
        selected_plan = next(
            (item for item in plans if str(item.get("id")) == str(plan)),
            None,
        )
        if selected_plan is None:
            raise ValueError("El plan seleccionado no existe.")
        plan_router = _related_id(selected_plan.get("router"))
        if plan_router is not None and str(plan_router) != str(router):
            raise ValueError("El plan seleccionado pertenece a otro router.")

    payload = {
        "nombre_completo": nombre,
        "usuario_pppoe": usuario,
        **({"password_pppoe": password} if password else {}),
        "plan": plan,
        "router": router,
        "estado": data.get("estado", "activo"),
        "direccion_ip_antena": ip_antena or None,
    }
    if payload["estado"] not in ("activo", "suspendido"):
        raise ValueError("Seleccione un estado válido para el cliente.")
    return payload


def clear_api_session(request):
    for key in (
        "mikrotik_api_token",
        "mikrotik_api_username",
        "mikrotik_api_role",
    ):
        request.session.pop(key, None)
    request.session.modified = True


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


class LoginView(APIViewMixin, TemplateView):
    template_name = "auth/login.html"

    def dispatch(self, request, *args, **kwargs):
        if request.session.get("mikrotik_api_token"):
            return redirect("dashboard_index")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        if not username or not password:
            messages.error(request, "Ingrese usuario y contraseña.")
            return redirect("login")

        try:
            response = self.api(request=request).login(username, password)
        except APIError as exc:
            self.api_error(request, exc)
            return redirect("login")

        token = response.get("token") or response.get("key")
        request.session["mikrotik_api_token"] = token
        request.session["mikrotik_api_username"] = response.get("username") or username
        request.session["mikrotik_api_role"] = self._api_role(response)
        messages.success(request, "Sesión iniciada correctamente.")
        return redirect("dashboard_index")

    @staticmethod
    def _api_role(payload):
        user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
        for source in (payload, user):
            for key in ("role", "rol", "role_name", "rol_nombre"):
                if source.get(key):
                    return str(source[key])
        return "Rol administrado por la API"


class LogoutView(View):
    def post(self, request, *args, **kwargs):
        clear_api_session(request)
        return redirect("login")


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
        except APIError as exc:
            context["api_error"] = str(exc)
            self.api_error(self.request, exc)
            if exc.status_code == 401:
                return context

        for key, path in (("planes", "planes/"), ("routers", "routers/")):
            try:
                context[key] = api.get_list(path)
            except APIError as exc:
                context[key] = []
                self.api_error(self.request, exc)
                if exc.status_code == 401:
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
        except APIError as exc:
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
        except APIError as exc:
            self.api_error(request, exc)
        return redirect("dashboard_index")


class ClientesListView(AuthenticatedAPIViewMixin, TemplateView):
    template_name = "pppoe/clientes.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["clientes"] = self.api().get_list("clientes-pppoe/")
        except APIError as exc:
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
        except APIError as exc:
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
        except APIError as exc:
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
        except APIError as exc:
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
        except APIError as exc:
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


class PlanCrearView(PlanFormMixin, AuthenticatedAPIViewMixin, TemplateView):
    template_name = "pppoe/plan_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(form_action="crear", form_data={"router_id": None})
        try:
            context["routers"] = self.normalize_routers(self.api().get_list("routers/"))
        except APIError as exc:
            context["routers"] = []
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
        except APIError as exc:
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
        except APIError as exc:
            context.update(form_data={}, routers=[], api_error=str(exc))
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
        except APIError as exc:
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
        except APIError as exc:
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
        except APIError as exc:
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
        except APIError as exc:
            self.api_error(request, exc)
        return redirect("clientes_list")


class ClienteEditarView(AuthenticatedAPIViewMixin, TemplateView):
    template_name = "pppoe/cliente_editar.html"

    @staticmethod
    def _related_id(value):
        if isinstance(value, dict):
            return value.get("id") or value.get("pk")
        return value

    def get_context_data(self, pk, **kwargs):
        context = super().get_context_data(**kwargs)
        api = self.api()
        context["cliente_id"] = pk

        try:
            context["cliente"] = api.get(f"clientes-pppoe/{pk}/")
            context["cliente_plan_id"] = self._related_id(context["cliente"].get("plan"))
            context["cliente_router_id"] = self._related_id(context["cliente"].get("router"))
            context["planes"] = self.normalize_plans(api.get_list("planes/"))
            context["routers"] = self.normalize_routers(api.get_list("routers/"))
        except APIError as exc:
            context.update(cliente=None, planes=[], routers=[], api_error=str(exc))
            self.api_error(self.request, exc)
        return context

    def post(self, request, pk, *args, **kwargs):
        try:
            planes = self.normalize_plans(self.api().get_list("planes/"))
            payload = _pppoe_payload(request.POST, plans=planes, require_password=False)
        except APIError as exc:
            self.api_error(request, exc)
            return redirect("cliente_editar", pk=pk)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("cliente_editar", pk=pk)

        password = request.POST.get("password_pppoe", "").strip()
        if password:
            payload["password_pppoe"] = password
        else:
            payload.pop("password_pppoe", None)

        try:
            self.api().patch(f"clientes-pppoe/{pk}/", payload)
            messages.success(request, "Cliente PPPoE actualizado correctamente.")
        except APIError as exc:
            self.api_error(request, exc)
        return redirect("clientes_list")


class ClientePingView(AuthenticatedAPIViewMixin, View):
    def post(self, request, pk, *args, **kwargs):
        try:
            response = self.api().post(f"clientes-pppoe/{pk}/ping/")
            detail = response.get("detail") if isinstance(response, dict) else None
            messages.success(request, detail or "Prueba de conexión enviada al cliente PPPoE.")
        except APIError as exc:
            self.api_error(request, exc)
        return redirect("clientes_list")


class ClientePatearView(AuthenticatedAPIViewMixin, View):
    def post(self, request, pk, *args, **kwargs):
        try:
            response = self.api().post(f"clientes-pppoe/{pk}/patear/")
            detail = response.get("detail") if isinstance(response, dict) else None
            messages.success(request, detail or "Sesión PPPoE desconectada correctamente.")
        except APIError as exc:
            self.api_error(request, exc)
        return redirect("clientes_list")


class RoutersListView(AuthenticatedAPIViewMixin, TemplateView):
    template_name = "network/routers.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["routers"] = self.normalize_routers(self.api().get_list("routers/"))
        except APIError as exc:
            context.update(routers=[], api_error=str(exc))
            self.api_error(self.request, exc)
        return context


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


class RouterCrearView(RouterFormMixin, AuthenticatedAPIViewMixin, TemplateView):
    template_name = "network/router_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            form_action="crear",
            form_data={"activo_checked": True, "puerto_api": 8728},
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
        except APIError as exc:
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
        except APIError as exc:
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
        except APIError as exc:
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
        except APIError as exc:
            context["api_error"] = str(exc)
            self.api_error(self.request, exc)
            return context

        try:
            estado = api.get(f"routers/{router_id}/estado/")
            context["estado"] = estado if isinstance(estado, dict) else {}
        except APIError as exc:
            context["api_error"] = str(exc)
            self.api_error(self.request, exc)
        return context


class RouterEliminarView(AuthenticatedAPIViewMixin, View):
    def post(self, request, router_id, *args, **kwargs):
        try:
            self.api().delete(f"routers/{router_id}/")
            messages.success(request, "Router eliminado correctamente.")
        except APIError as exc:
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
        except APIError as exc:
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
        context.update(router_id=router_id, router={}, consumo=[], total=0, tipo="consumo")
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
        except APIError as exc:
            context["api_error"] = str(exc)
            self.api_error(self.request, exc)
        return context


class RouterLeasesView(AuthenticatedAPIViewMixin, TemplateView):
    template_name = "network/router_monitoreo.html"

    def get_context_data(self, router_id, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(router_id=router_id, router={}, leases=[], total=0, tipo="leases")
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
        except APIError as exc:
            context["api_error"] = str(exc)
            self.api_error(self.request, exc)
        return context


class ClientesRedListView(AuthenticatedAPIViewMixin, TemplateView):
    template_name = "network/clientes_red.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["clientes"] = self.api().get_list("clientes-red/")
        except APIError as exc:
            context.update(clientes=[], api_error=str(exc))
            self.api_error(self.request, exc)
        return context


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


class ClienteRedCrearView(ClienteRedFormMixin, AuthenticatedAPIViewMixin, TemplateView):
    template_name = "network/cliente_red_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(form_action="crear", cliente={}, form_data={})
        try:
            context.update(self.get_catalogs(self.api()))
        except APIError as exc:
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
        except APIError as exc:
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
        except APIError as exc:
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
        except APIError as exc:
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
        except APIError as exc:
            self.api_error(request, exc)
        return redirect("clientes_red_list")


class ClienteRedEliminarView(AuthenticatedAPIViewMixin, View):
    def post(self, request, pk, *args, **kwargs):
        try:
            self.api().delete(f"clientes-red/{pk}/")
            messages.success(request, "Cliente DHCP/IP fija eliminado correctamente.")
        except APIError as exc:
            self.api_error(request, exc)
        return redirect("clientes_red_list")


class EnlacesISPListView(AuthenticatedAPIViewMixin, TemplateView):
    template_name = "network/enlaces.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["enlaces"] = self.api().get_list("enlaces-isp/")
        except APIError as exc:
            context.update(enlaces=[], api_error=str(exc))
            self.api_error(self.request, exc)
        return context


class InterfacesListView(AuthenticatedAPIViewMixin, TemplateView):
    template_name = "network/interfaces.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["interfaces"] = self.api().get_list("interfaces/")
        except APIError as exc:
            context.update(interfaces=[], api_error=str(exc))
            self.api_error(self.request, exc)
        return context


class ClienteEliminarView(AuthenticatedAPIViewMixin, View):
    def post(self, request, pk, *args, **kwargs):
        try:
            self.api().delete(f"clientes-pppoe/{pk}/")
            messages.success(request, "Cliente eliminado correctamente.")
        except APIError as exc:
            self.api_error(request, exc)
        return redirect("clientes_list")

from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import TemplateView, View
from ..api_client import APIError
from ..errores import MENSAJE_API_CAIDA, mensaje_usuario
from ..mixins import APIViewMixin
from ..utils import clear_api_session


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
            # El mensaje depende del código, no del texto del error (antes
            # se adivinaba buscando "Unable to log in..." o "400" en el
            # texto: un 500 de la API se mostraba como "No se pudo
            # conectar", y cualquier 400 como credenciales incorrectas).
            # 400 del login = credenciales incorrectas; el resto, el
            # mensaje llano según el código.
            if exc.status_code == 400:
                user_message = "El usuario o la contraseña son incorrectos."
            else:
                user_message = mensaje_usuario(exc)
            messages.error(request, user_message)
            return redirect("login")
        except Exception:
            # Un fallo que no es de la API (por ejemplo, la web sin red):
            # genérico, sin exponer el detalle.
            messages.error(request, MENSAJE_API_CAIDA)
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


class LogoutView(APIViewMixin, View):
    def post(self, request, *args, **kwargs):
        # Mejor esfuerzo: si la API ya permite revocar el token, se revoca
        # para que no siga valiendo después de cerrar sesión. Si la API
        # responde 404/405 en las rutas candidatas o no responde, se cierra
        # la sesión local igualmente: el cierre de sesión nunca debe fallar
        # por eso.
        if request.session.get("mikrotik_api_token"):
            try:
                self.api(request=request).revocar_token()
            except Exception:
                pass
        clear_api_session(request)
        return redirect("login")

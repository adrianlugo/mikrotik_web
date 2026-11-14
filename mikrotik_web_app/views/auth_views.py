from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import TemplateView, View
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
        except Exception as exc:
            # Intentamos extraer el mensaje real del error de la API
            error_msg = str(exc)
            
            if "Unable to log in with provided credentials" in error_msg or "400" in error_msg:
                user_message = "El usuario o la contraseña son incorrectos."
            else:
                user_message = "No se pudo conectar con el servidor de la API."
                
            messages.error(request, user_message)
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
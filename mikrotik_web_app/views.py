from django.views.generic import TemplateView, View
from django.shortcuts import redirect
import requests
import logging

logger = logging.getLogger(__name__)

class DashboardIndexView(TemplateView):
    template_name = 'pppoe/index.html' 

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        url_activos = 'http://localhost:8000/api/clientes-pppoe/activos/'  
        url_planes = 'http://localhost:8000/api/planes/' # <-- Asumiendo que tu endpoint de planes es este

        # 1. Consultar usuarios activos
        try:
            response = requests.get(url_activos, timeout=5)
            if response.status_code == 200:
                api_data = response.json()
                context['router_nombre'] = api_data.get('router', 'Desconocido')
                context['total_conectados'] = api_data.get('total_conectados', 0)
                context['conexiones'] = api_data.get('conexiones', [])
                context['api_error'] = False
            else:
                context['api_error'] = True
                context['error_msg'] = "No se pudieron obtener datos del Router."
        except requests.exceptions.RequestException:
            context['api_error'] = True
            context['error_msg'] = "Sin comunicación con el servidor de la API."
            context['total_conectados'] = 0
            context['conexiones'] = []

        # 2.Traer los planes para el desplegable (Select)
        try:
            # Si tu endpoint de la API requiere el formato clásico de listado de DRF
            response_planes = requests.get(url_planes, timeout=5)
            if response_planes.status_code == 200:
                context['planes'] = response_planes.json()  # Guarda la lista de planes
            else:
                context['planes'] = []
        except requests.exceptions.RequestException:
            context['planes'] = []

        return context

    def post(self, request, *args, **kwargs):
        """Procesa el envío del formulario para registrar clientes en caliente"""
        usuario = request.POST.get('usuario')
        password = request.POST.get('password')
        plan_raw  = request.POST.get('plan')
        nombre = request.POST.get('nombre_completo')

        # Convertimos el plan a un número entero seguro para evitar desajustes en la API
        try:
            plan_id = int(plan_raw) if plan_raw else None
        except ValueError:
            plan_id = None

        # El endpoint de creación de tu proyecto API
        url_crear = 'http://localhost:8000/api/clientes-pppoe/'
        
        payload = {
            "usuario_pppoe": usuario,
            "password_pppoe": password,
            "nombre_completo": nombre,
            "plan": plan_id,          # Debe coincidir con el ID o nombre del Plan en tu BD
            "router": 1,           # Asumimos que tu CHR es el ID 1 registrado
            "estado": "activo"
        }

        try:
            response = requests.post(url_crear, json=payload, timeout=5)
            if response.status_code == 201:
                return redirect('dashboard_index')
            else:
                context = self.get_context_data()
                context['api_error'] = True
                context['error_msg'] = f"Fallo al registrar en MikroTik: {response.text}"
                return self.render_to_response(context)
        except requests.exceptions.RequestException as e:
            context = self.get_context_data()
            context['api_error'] = True
            context['error_msg'] = f"Error de conexión: {str(e)}"
            return self.render_to_response(context)


class SincronizarMikrotikView(View):
    def post(self, request, *args, **kwargs):
        """Envía la instrucción POST a la API para importar secretos de Winbox en caliente"""
        url_importar = 'http://localhost:8000/api/clientes-pppoe/importar-desde-mikrotik/'
        
        try:
            response = requests.post(url_importar, timeout=10)
            # No importa si da éxito o error, recargamos la página principal para refrescar los datos
            return redirect('dashboard_index')
        except requests.exceptions.RequestException:
            return redirect('dashboard_index')


class ClientesListView(TemplateView):
    template_name = 'pppoe/clientes.html'  # Apunta a la nueva plantilla

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 🔗 Consultamos el endpoint de listado completo de clientes
        url_clientes = 'http://localhost:8000/api/clientes-pppoe/'
        
        try:
            response = requests.get(url_clientes, timeout=5)
            if response.status_code == 200:
                # La API nos devuelve la lista completa de objetos cliente
                context['clientes'] = response.json()
                context['api_error'] = False
            else:
                context['api_error'] = True
                context['error_msg'] = "No se pudo recuperar el listado de clientes desde la API."
                context['clientes'] = []
        except requests.exceptions.RequestException:
            context['api_error'] = True
            context['error_msg'] = "Error de comunicación con el servidor de la API."
            context['clientes'] = []

        return context

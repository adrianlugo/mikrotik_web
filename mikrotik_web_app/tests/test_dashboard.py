from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.contrib.messages import get_messages
from django.test.client import Client
from mikrotik_web_app.api_client import APIError

class DashboardViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        session = self.client.session
        session["mikrotik_api_token"] = "token-de-prueba"
        session["mikrotik_api_username"] = "operador"
        session.save()

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get")
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list")
    def test_dashboard_reads_api_collections(self, get_list, get):
        get.return_value = {"router": "CHR", "total_conectados": 0, "conexiones": []}
        get_list.return_value = []
        response = self.client.get(reverse("dashboard_index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vista General")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get")
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", return_value=[])
    def test_dashboard_reads_router_names_from_routers_list(self, get_list, get):
        # La API devuelve `routers` como lista de nombres, no `router` ni
        # `router_nombre`: el dashboard debe mostrar esos nombres y nunca
        # "Ninguno"/"Desconocido" cuando hay datos.
        get.return_value = {
            "routers": ["CHR Principal", "CHR Sucursal"],
            "total_conectados": 2,
            "conexiones": [
                {"usuario_pppoe": "cliente1"},
                {"usuario_pppoe": "cliente2"},
            ],
            "errores": [],
        }
        response = self.client.get(reverse("dashboard_index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CHR Principal")
        self.assertContains(response, "CHR Sucursal")
        self.assertNotContains(response, "Ninguno")
        self.assertNotContains(response, "Desconocido")
        self.assertEqual(response.context["router_nombre"], "CHR Principal, CHR Sucursal")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get")
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list")
    def test_dashboard_counts_real_total_clientes(self, get_list, get):
        get.return_value = {"routers": ["CHR Principal"], "total_conectados": 1, "conexiones": []}
        get_list.side_effect = [
            [{"id": 2, "nombre_perfil": "Plan Hogar", "router": 3}],
            [{"id": 3, "nombre": "CHR Principal"}],
            [
                {"id": 1, "usuario_pppoe": "cliente1"},
                {"id": 2, "usuario_pppoe": "cliente2"},
                {"id": 3, "usuario_pppoe": "cliente3"},
            ],
        ]
        response = self.client.get(reverse("dashboard_index"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_clientes"], 3)

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", return_value=[])
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get", side_effect=APIError("El router no responde.", status_code=502))
    def test_dashboard_shows_unavailable_when_activos_fails(self, get, get_list):
        # Si la API devuelve 502, no se inventa un 0 de conectados.
        response = self.client.get(reverse("dashboard_index"))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["total_conectados"])
        self.assertTrue(response.context["activos_no_disponibles"])
        self.assertContains(response, "No disponible")
        self.assertNotContains(response, "No se detectaron usuarios navegando")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
    def test_router_sync_action(self, post):
        response = self.client.post(reverse("sincronizar_mikrotik"), {"router": "4"})

        self.assertRedirects(response, reverse("dashboard_index"), fetch_redirect_response=False)
        post.assert_called_once_with("routers/4/sincronizar/")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", return_value=[])
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get", side_effect=APIError("La sesión de la API expiró.", status_code=401))
    def test_expired_api_token_redirects_to_login(self, get, get_list):
        # El token expirado (401) limpia la sesión y redirige a login con
        # un mensaje claro, en vez de dejar el dashboard con listas vacías.
        response = self.client.get(reverse("dashboard_index"))

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("mikrotik_api_token", self.client.session)
        mensajes = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertIn("Tu sesión caducó. Inicia sesión de nuevo.", mensajes)

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", return_value=[])
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get", side_effect=APIError("No tiene permisos para consultar el recurso.", status_code=403))
    def test_forbidden_api_response_keeps_session(self, get, get_list):
        response = self.client.get(reverse("dashboard_index"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("mikrotik_api_token", self.client.session)
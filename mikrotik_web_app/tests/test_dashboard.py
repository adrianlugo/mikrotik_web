from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
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

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
    def test_router_sync_action(self, post):
        response = self.client.post(reverse("sincronizar_mikrotik"), {"router": "4"})

        self.assertRedirects(response, reverse("dashboard_index"), fetch_redirect_response=False)
        post.assert_called_once_with("routers/4/sincronizar/")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", return_value=[])
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get", side_effect=APIError("La sesión de la API expiró.", status_code=401))
    def test_expired_api_token_is_cleared(self, get, get_list):
        response = self.client.get(reverse("dashboard_index"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("mikrotik_api_token", self.client.session)

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", return_value=[])
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get", side_effect=APIError("No tiene permisos para consultar el recurso.", status_code=403))
    def test_forbidden_api_response_keeps_session(self, get, get_list):
        response = self.client.get(reverse("dashboard_index"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("mikrotik_api_token", self.client.session)
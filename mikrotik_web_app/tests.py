from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


class WebAPITestCase(TestCase):
    @patch("mikrotik_web_app.views.MikrotikAPIClient.get")
    @patch("mikrotik_web_app.views.MikrotikAPIClient.get_list")
    def test_dashboard_reads_api_collections(self, get_list, get):
        get.return_value = {"router": "CHR", "total_conectados": 0, "conexiones": []}
        get_list.return_value = []
        response = self.client.get(reverse("dashboard_index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vista General")

    @patch("mikrotik_web_app.views.MikrotikAPIClient.post")
    def test_client_status_action(self, post):
        response = self.client.post(reverse("cliente_estado", args=[7]))
        self.assertRedirects(response, reverse("clientes_list"), fetch_redirect_response=False)
        post.assert_called_once_with("clientes-pppoe/7/cambiar-estado/")

    @patch("mikrotik_web_app.views.MikrotikAPIClient.delete")
    def test_client_delete_action(self, delete):
        response = self.client.post(reverse("cliente_eliminar", args=[7]))
        self.assertRedirects(response, reverse("clientes_list"), fetch_redirect_response=False)
        delete.assert_called_once_with("clientes-pppoe/7/")

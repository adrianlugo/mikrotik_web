from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.test.client import Client

class RouterViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        session = self.client.session
        session["mikrotik_api_token"] = "token-de-prueba"
        session["mikrotik_api_username"] = "operador"
        session.save()

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", return_value=[
        {
            "id": 4,
            "nombre": "CHR Principal",
            "ip_address": "192.168.88.1",
            "puerto_api": 8729,
            "usuario": "api",
            "activo": True,
        }
    ])
    def test_routers_page_reads_enabled_state(self, get_list):
        response = self.client.get(reverse("routers_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CHR Principal")
        self.assertContains(response, "Habilitado")
        get_list.assert_called_once_with("routers/")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
    def test_create_router_payload(self, post):
        response = self.client.post(
            reverse("router_crear"),
            {
                "nombre": "CHR Sucursal",
                "ip_address": "192.168.88.2",
                "puerto_api": "8729",
                "usuario": "api_sucursal",
                "password": "secreto-api",
                "activo": "on",
            },
        )

        self.assertRedirects(response, reverse("routers_list"), fetch_redirect_response=False)
        post.assert_called_once_with(
            "routers/",
            {
                "nombre": "CHR Sucursal",
                "ip_address": "192.168.88.2",
                "puerto_api": 8729,
                "usuario": "api_sucursal",
                "activo": True,
                "password": "secreto-api",
            },
        )

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.patch")
    def test_edit_router_without_password_preserves_existing_password(self, patch_client):
        response = self.client.post(
            reverse("router_editar", args=[4]),
            {
                "nombre": "CHR Principal",
                "ip_address": "192.168.88.1",
                "puerto_api": "8729",
                "usuario": "api",
                "password": "",
                "activo": "on",
            },
        )

        self.assertRedirects(response, reverse("router_detalle", args=[4]), fetch_redirect_response=False)
        patch_client.assert_called_once_with(
            "routers/4/",
            {
                "nombre": "CHR Principal",
                "ip_address": "192.168.88.1",
                "puerto_api": 8729,
                "usuario": "api",
                "activo": True,
            },
        )

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get")
    def test_edit_router_page_preserves_disabled_state(self, get):
        get.return_value = {
            "id": 4,
            "nombre": "CHR Inactivo",
            "ip_address": "192.168.88.3",
            "puerto_api": 8729,
            "usuario": "api",
            "activo": False,
        }

        response = self.client.get(reverse("router_editar", args=[4]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Editar router MikroTik")
        self.assertNotContains(response, 'name="activo" checked')
        get.assert_called_once_with("routers/4/")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
    def test_router_actions_use_remote_api_paths(self, post):
        post.side_effect = [
            {"status": "success", "detail": "Conexión correcta"},
            {"status": "success", "detail": "Sincronización completa"},
            {"status": "success", "detail": "Colas reparadas"},
        ]

        for route_name, expected_path in (
            ("router_verificar", "routers/4/verificar-conexion/"),
            ("router_sincronizar", "routers/4/sincronizar/"),
            ("router_reparar_colas", "routers/4/reparar-colas/"),
        ):
            response = self.client.post(reverse(route_name, args=[4]))
            self.assertRedirects(response, reverse("router_detalle", args=[4]), fetch_redirect_response=False)

        self.assertEqual(
            [call.args[0] for call in post.call_args_list],
            [
                "routers/4/verificar-conexion/",
                "routers/4/sincronizar/",
                "routers/4/reparar-colas/",
            ],
        )

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get")
    def test_router_consumption_normalizes_routeros_fields(self, get):
        get.side_effect = [
            {
                "id": 4,
                "nombre": "CHR Principal",
                "ip_address": "192.168.88.1",
            },
            {
                "router": "CHR Principal",
                "total_colas": 1,
                "colas": [
                    {
                        "name": "Cliente 20M",
                        "parent": "Plan-20M",
                        "target": "192.168.88.50/32",
                        "max-limit": "20M/20M",
                        "rate": "1M/1M",
                        "disabled": "false",
                    }
                ],
            },
        ]

        response = self.client.get(reverse("router_consumo", args=[4]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente 20M")
        self.assertContains(response, "20M/20M")
        self.assertContains(response, "192.168.88.50/32")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get")
    def test_router_dhcp_leases_normalizes_mac_address(self, get):
        get.side_effect = [
            {
                "id": 4,
                "nombre": "CHR Principal",
                "ip_address": "192.168.88.1",
            },
            {
                "router": "CHR Principal",
                "total": 1,
                "leases": [
                    {
                        "address": "192.168.88.50",
                        "mac-address": "AA:BB:CC:DD:EE:50",
                        "server": "dhcp1",
                        "status": "bound",
                        "comment": "Cliente oficina",
                    }
                ],
            },
        ]

        response = self.client.get(reverse("router_leases", args=[4]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AA:BB:CC:DD:EE:50")
        self.assertContains(response, "Cliente oficina")
from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.test.client import Client

class PPPoEViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        session = self.client.session
        session["mikrotik_api_token"] = "token-de-prueba"
        session["mikrotik_api_username"] = "operador"
        session.save()

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get", return_value={"id": 7, "estado": "activo"})
    def test_client_status_action(self, get, post):
        response = self.client.post(reverse("cliente_estado", args=[7]))
        self.assertRedirects(response, reverse("clientes_list"), fetch_redirect_response=False)
        get.assert_called_once_with("clientes-pppoe/7/")
        post.assert_called_once_with(
            "clientes-pppoe/7/cambiar-estado/",
            {"estado": "suspendido"},
        )

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", side_effect=[
        [{"id": 3, "nombre": "Router Principal"}],
        [{"id": 2, "nombre_perfil": "Plan Hogar", "router": 3}],
    ])
    def test_client_create_page(self, get_list):
        response = self.client.get(reverse("cliente_crear"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nuevo cliente PPPoE")
        self.assertEqual(get_list.call_count, 2)

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", return_value=[{"id": 2, "nombre_perfil": "Plan Hogar", "router": 3}])
    def test_client_create_action(self, get_list, post):
        response = self.client.post(
            reverse("cliente_crear"),
            {
                "nombre_completo": "Cliente Nuevo",
                "usuario_pppoe": "cliente_nuevo",
                "password_pppoe": "secreto123",
                "direccion_ip_antena": "192.168.50.10",
                "plan": "2",
                "router": "3",
                "estado": "activo",
            },
        )

        self.assertRedirects(response, reverse("clientes_list"), fetch_redirect_response=False)
        post.assert_called_once_with(
            "clientes-pppoe/",
            {
                "nombre_completo": "Cliente Nuevo",
                "usuario_pppoe": "cliente_nuevo",
                "password_pppoe": "secreto123",
                "plan": 2,
                "router": 3,
                "estado": "activo",
                "direccion_ip_antena": "192.168.50.10",
            },
        )

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", return_value=[{"id": 2, "nombre_perfil": "Plan Hogar", "router": 8}])
    def test_client_create_rejects_plan_from_other_router(self, get_list, post):
        response = self.client.post(
            reverse("cliente_crear"),
            {
                "nombre_completo": "Cliente Nuevo",
                "usuario_pppoe": "cliente_nuevo",
                "password_pppoe": "secreto123",
                "plan": "2",
                "router": "3",
                "estado": "activo",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "pertenece a otro router", status_code=400)
        post.assert_not_called()

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.delete")
    def test_client_delete_action(self, delete):
        response = self.client.post(reverse("cliente_eliminar", args=[7]))
        self.assertRedirects(response, reverse("clientes_list"), fetch_redirect_response=False)
        delete.assert_called_once_with("clientes-pppoe/7/")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", return_value=[])
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get")
    def test_client_edit_page(self, get, get_list):
        get.return_value = {
            "id": 7,
            "nombre_completo": "Cliente Prueba",
            "usuario_pppoe": "cliente",
            "plan": 2,
            "router": 3,
            "estado": "activo",
        }

        response = self.client.get(reverse("cliente_editar", args=[7]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Editar cliente PPPoE")
        get.assert_called_once_with("clientes-pppoe/7/")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.patch")
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", return_value=[{"id": 2, "nombre_perfil": "Plan Hogar", "router": 3}])
    def test_client_edit_action(self, get_list, patch_client):
        response = self.client.post(
            reverse("cliente_editar", args=[7]),
            {
                "nombre_completo": "Cliente Actualizado",
                "usuario_pppoe": "cliente2",
                "password_pppoe": "",
                "plan": "2",
                "router": "3",
                "estado": "activo",
            },
        )

        self.assertRedirects(response, reverse("clientes_list"), fetch_redirect_response=False)
        patch_client.assert_called_once_with(
            "clientes-pppoe/7/",
            {
                "nombre_completo": "Cliente Actualizado",
                "usuario_pppoe": "cliente2",
                "estado": "activo",
                "plan": 2,
                "router": 3,
                "direccion_ip_antena": None,
            },
        )

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
    def test_client_ping_action(self, post):
        post.return_value = {"detail": "El cliente responde"}

        response = self.client.post(reverse("cliente_ping", args=[7]))

        self.assertRedirects(response, reverse("clientes_list"), fetch_redirect_response=False)
        post.assert_called_once_with("clientes-pppoe/7/ping/")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
    def test_client_kick_action(self, post):
        post.return_value = {"detail": "Sesión desconectada"}

        response = self.client.post(reverse("cliente_patear", args=[7]))

        self.assertRedirects(response, reverse("clientes_list"), fetch_redirect_response=False)
        post.assert_called_once_with("clientes-pppoe/7/patear/")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", side_effect=[
        [
            {
                "id": 8,
                "nombre_perfil": "Plan 20M",
                "cola_padre": "Plan-20M",
                "subida_mbps": 20,
                "bajada_mbps": 20,
                "router": 4,
            }
        ],
        [{"id": 4, "nombre": "CHR Principal", "ip_address": "192.168.88.1"}],
    ])
    def test_plans_page_uses_real_api_fields(self, get_list):
        response = self.client.get(reverse("planes_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Plan 20M")
        self.assertContains(response, "CHR Principal")
        self.assertEqual(
            [call.args[0] for call in get_list.call_args_list],
            ["planes/", "routers/"],
        )

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
    def test_create_plan_uses_real_api_payload(self, post):
        response = self.client.post(
            reverse("plan_crear"),
            {
                "nombre_perfil": "Plan 30M",
                "cola_padre": "Plan-30M",
                "subida_mbps": "30",
                "bajada_mbps": "30",
                "router": "4",
            },
        )

        self.assertRedirects(response, reverse("planes_list"), fetch_redirect_response=False)
        post.assert_called_once_with(
            "planes/",
            {
                "nombre_perfil": "Plan 30M",
                "cola_padre": "Plan-30M",
                "subida_mbps": 30,
                "bajada_mbps": 30,
                "router": 4,
            },
        )

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", return_value=[
        {"id": 4, "nombre": "CHR Principal", "ip_address": "192.168.88.1"},
    ])
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get")
    def test_edit_plan_page_selects_related_router(self, get, get_list):
        get.return_value = {
            "id": 8,
            "nombre_perfil": "Plan 20M",
            "cola_padre": "Plan-20M",
            "subida_mbps": 20,
            "bajada_mbps": 20,
            "router": 4,
        }

        response = self.client.get(reverse("plan_editar", args=[8]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Editar plan de internet")
        self.assertContains(response, 'value="4" selected')
        get.assert_called_once_with("planes/8/")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.patch")
    def test_edit_plan_action(self, patch_client):
        response = self.client.post(
            reverse("plan_editar", args=[8]),
            {
                "nombre_perfil": "Plan 40M",
                "cola_padre": "Plan-40M",
                "subida_mbps": "40",
                "bajada_mbps": "40",
                "router": "4",
            },
        )

        self.assertRedirects(response, reverse("planes_list"), fetch_redirect_response=False)
        patch_client.assert_called_once_with(
            "planes/8/",
            {
                "nombre_perfil": "Plan 40M",
                "cola_padre": "Plan-40M",
                "subida_mbps": 40,
                "bajada_mbps": 40,
                "router": 4,
            },
        )
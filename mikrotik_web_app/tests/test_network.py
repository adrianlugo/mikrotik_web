from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.test.client import Client

class NetworkViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        session = self.client.session
        session["mikrotik_api_token"] = "token-de-prueba"
        session["mikrotik_api_username"] = "operador"
        session.save()

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", return_value=[{
        "id": 12,
        "nombre": "Cliente DHCP",
        "tipo": "dhcp",
        "direccion_ip": "192.168.88.50",
        "estado": "activo",
    }])
    def test_clients_red_page_reads_api_collection(self, get_list):
        response = self.client.get(reverse("clientes_red_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente DHCP")
        get_list.assert_called_once_with("clientes-red/")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
    def test_create_client_red(self, post):
        response = self.client.post(
            reverse("cliente_red_crear"),
            {
                "nombre": "Cliente Oficina",
                "tipo": "dhcp",
                "direccion_ip": "192.168.88.51",
                "direccion_mac": "AA:BB:CC:DD:EE:01",
                "interfaz_mikrotik": "bridge-lan",
                "servidor_dhcp": "dhcp1",
                "plan": "2",
                "router": "3",
                "estado": "activo",
            },
        )

        self.assertRedirects(response, reverse("clientes_red_list"), fetch_redirect_response=False)
        post.assert_called_once_with(
            "clientes-red/",
            {
                "nombre": "Cliente Oficina",
                "tipo": "dhcp",
                "direccion_ip": "192.168.88.51",
                "direccion_mac": "AA:BB:CC:DD:EE:01",
                "interfaz_mikrotik": "bridge-lan",
                "servidor_dhcp": "dhcp1",
                "estado": "activo",
                "plan": 2,
                "router": 3,
            },
        )

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", return_value=[])
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get")
    def test_edit_client_red_page(self, get, get_list):
        get.return_value = {
            "id": 12,
            "nombre": "Cliente IP fija",
            "tipo": "ip_fija",
            "direccion_ip": "192.168.88.52",
            "direccion_mac": "AA:BB:CC:DD:EE:02",
            "plan": 2,
            "router": 3,
            "estado": "activo",
        }

        response = self.client.get(reverse("cliente_red_editar", args=[12]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Editar cliente DHCP / IP fija")
        get.assert_called_once_with("clientes-red/12/")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.patch")
    def test_edit_client_red_action(self, patch_client):
        response = self.client.post(
            reverse("cliente_red_editar", args=[12]),
            {
                "nombre": "Cliente Actualizado",
                "tipo": "ip_fija",
                "direccion_ip": "192.168.88.53",
                "direccion_mac": "AA:BB:CC:DD:EE:03",
                "interfaz_mikrotik": "bridge-lan",
                "servidor_dhcp": "",
                "plan": "2",
                "router": "3",
                "estado": "activo",
            },
        )

        self.assertRedirects(response, reverse("clientes_red_list"), fetch_redirect_response=False)
        patch_client.assert_called_once_with(
            "clientes-red/12/",
            {
                "nombre": "Cliente Actualizado",
                "tipo": "ip_fija",
                "direccion_ip": "192.168.88.53",
                "direccion_mac": "AA:BB:CC:DD:EE:03",
                "interfaz_mikrotik": "bridge-lan",
                "servidor_dhcp": "",
                "estado": "activo",
                "plan": 2,
                "router": 3,
            },
        )

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
    def test_repair_client_red_queue(self, post):
        response = self.client.post(reverse("cliente_red_reparar_cola", args=[12]))

        self.assertRedirects(response, reverse("clientes_red_list"), fetch_redirect_response=False)
        post.assert_called_once_with("clientes-red/12/crear-cola/")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.delete")
    def test_delete_client_red(self, delete):
        response = self.client.post(reverse("cliente_red_eliminar", args=[12]))

        self.assertRedirects(response, reverse("clientes_red_list"), fetch_redirect_response=False)
        delete.assert_called_once_with("clientes-red/12/")
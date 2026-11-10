from unittest.mock import Mock, patch

from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from .api_client import APIError, MikrotikAPIClient


class WebAPITestCase(TestCase):
    def setUp(self):
        session = self.client.session
        session["mikrotik_api_token"] = "token-de-prueba"
        session["mikrotik_api_username"] = "operador"
        session.save()

    @patch("mikrotik_web_app.views.MikrotikAPIClient.get")
    @patch("mikrotik_web_app.views.MikrotikAPIClient.get_list")
    def test_dashboard_reads_api_collections(self, get_list, get):
        get.return_value = {"router": "CHR", "total_conectados": 0, "conexiones": []}
        get_list.return_value = []
        response = self.client.get(reverse("dashboard_index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vista General")

    @patch("mikrotik_web_app.views.MikrotikAPIClient.post")
    @patch(
        "mikrotik_web_app.views.MikrotikAPIClient.get",
        return_value={"id": 7, "estado": "activo"},
    )
    def test_client_status_action(self, get, post):
        response = self.client.post(reverse("cliente_estado", args=[7]))
        self.assertRedirects(response, reverse("clientes_list"), fetch_redirect_response=False)
        get.assert_called_once_with("clientes-pppoe/7/")
        post.assert_called_once_with(
            "clientes-pppoe/7/cambiar-estado/",
            {"estado": "suspendido"},
        )

    @patch(
        "mikrotik_web_app.views.MikrotikAPIClient.get_list",
        side_effect=[
            [{"id": 3, "nombre": "Router Principal"}],
            [{"id": 2, "nombre_perfil": "Plan Hogar", "router": 3}],
        ],
    )
    def test_client_create_page(self, get_list):
        response = self.client.get(reverse("cliente_crear"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nuevo cliente PPPoE")
        self.assertEqual(get_list.call_count, 2)

    @patch("mikrotik_web_app.views.MikrotikAPIClient.post")
    @patch(
        "mikrotik_web_app.views.MikrotikAPIClient.get_list",
        return_value=[{"id": 2, "nombre_perfil": "Plan Hogar", "router": 3}],
    )
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

    @patch("mikrotik_web_app.views.MikrotikAPIClient.post")
    @patch(
        "mikrotik_web_app.views.MikrotikAPIClient.get_list",
        return_value=[{"id": 2, "nombre_perfil": "Plan Hogar", "router": 8}],
    )
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

    @patch("mikrotik_web_app.views.MikrotikAPIClient.delete")
    def test_client_delete_action(self, delete):
        response = self.client.post(reverse("cliente_eliminar", args=[7]))
        self.assertRedirects(response, reverse("clientes_list"), fetch_redirect_response=False)
        delete.assert_called_once_with("clientes-pppoe/7/")

    @patch("mikrotik_web_app.views.MikrotikAPIClient.get_list", return_value=[])
    @patch("mikrotik_web_app.views.MikrotikAPIClient.get")
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

    @patch("mikrotik_web_app.views.MikrotikAPIClient.patch")
    @patch(
        "mikrotik_web_app.views.MikrotikAPIClient.get_list",
        return_value=[{"id": 2, "nombre_perfil": "Plan Hogar", "router": 3}],
    )
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

    @patch("mikrotik_web_app.views.MikrotikAPIClient.post")
    def test_client_ping_action(self, post):
        post.return_value = {"detail": "El cliente responde"}

        response = self.client.post(reverse("cliente_ping", args=[7]))

        self.assertRedirects(response, reverse("clientes_list"), fetch_redirect_response=False)
        post.assert_called_once_with("clientes-pppoe/7/ping/")

    @patch("mikrotik_web_app.views.MikrotikAPIClient.post")
    def test_client_kick_action(self, post):
        post.return_value = {"detail": "Sesión desconectada"}

        response = self.client.post(reverse("cliente_patear", args=[7]))

        self.assertRedirects(response, reverse("clientes_list"), fetch_redirect_response=False)
        post.assert_called_once_with("clientes-pppoe/7/patear/")

    @patch("mikrotik_web_app.views.MikrotikAPIClient.post")
    def test_router_sync_action(self, post):
        response = self.client.post(reverse("sincronizar_mikrotik"), {"router": "4"})

        self.assertRedirects(response, reverse("dashboard_index"), fetch_redirect_response=False)
        post.assert_called_once_with("routers/4/sincronizar/")

    @patch(
        "mikrotik_web_app.views.MikrotikAPIClient.get_list",
        side_effect=[
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
        ],
    )
    def test_plans_page_uses_real_api_fields(self, get_list):
        response = self.client.get(reverse("planes_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Plan 20M")
        self.assertContains(response, "CHR Principal")
        self.assertEqual(
            [call.args[0] for call in get_list.call_args_list],
            ["planes/", "routers/"],
        )

    @patch("mikrotik_web_app.views.MikrotikAPIClient.post")
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

    @patch("mikrotik_web_app.views.MikrotikAPIClient.get_list", return_value=[
        {"id": 4, "nombre": "CHR Principal", "ip_address": "192.168.88.1"},
    ])
    @patch("mikrotik_web_app.views.MikrotikAPIClient.get")
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

    @patch("mikrotik_web_app.views.MikrotikAPIClient.patch")
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

    @patch("mikrotik_web_app.views.MikrotikAPIClient.get_list", return_value=[
        {
            "id": 4,
            "nombre": "CHR Principal",
            "ip_address": "192.168.88.1",
            "puerto_api": 8728,
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

    @patch("mikrotik_web_app.views.MikrotikAPIClient.post")
    def test_create_router_payload(self, post):
        response = self.client.post(
            reverse("router_crear"),
            {
                "nombre": "CHR Sucursal",
                "ip_address": "192.168.88.2",
                "puerto_api": "8728",
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
                "puerto_api": 8728,
                "usuario": "api_sucursal",
                "activo": True,
                "password": "secreto-api",
            },
        )

    @patch("mikrotik_web_app.views.MikrotikAPIClient.patch")
    def test_edit_router_without_password_preserves_existing_password(self, patch_client):
        response = self.client.post(
            reverse("router_editar", args=[4]),
            {
                "nombre": "CHR Principal",
                "ip_address": "192.168.88.1",
                "puerto_api": "8728",
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
                "puerto_api": 8728,
                "usuario": "api",
                "activo": True,
            },
        )

    @patch("mikrotik_web_app.views.MikrotikAPIClient.get")
    def test_edit_router_page_preserves_disabled_state(self, get):
        get.return_value = {
            "id": 4,
            "nombre": "CHR Inactivo",
            "ip_address": "192.168.88.3",
            "puerto_api": 8728,
            "usuario": "api",
            "activo": False,
        }

        response = self.client.get(reverse("router_editar", args=[4]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Editar router MikroTik")
        self.assertNotContains(response, 'name="activo" checked')
        get.assert_called_once_with("routers/4/")

    @patch("mikrotik_web_app.views.MikrotikAPIClient.post")
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

    @patch("mikrotik_web_app.views.MikrotikAPIClient.get")
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

    @patch("mikrotik_web_app.views.MikrotikAPIClient.get")
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

    def test_dashboard_redirects_to_login_without_session(self):
        self.client.cookies.clear()
        self.client.session.flush()

        response = self.client.get(reverse("dashboard_index"))

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)

    @patch("mikrotik_web_app.views.MikrotikAPIClient.login")
    def test_login_stores_api_token_and_role(self, login):
        session = self.client.session
        session.pop("mikrotik_api_token", None)
        session.pop("mikrotik_api_username", None)
        session.save()
        login.return_value = {
            "token": "token-obtenido",
            "username": "operador",
            "rol": "Administrador",
        }

        response = self.client.post(
            reverse("login"),
            {"username": "operador", "password": "clave"},
        )

        self.assertRedirects(response, reverse("dashboard_index"), fetch_redirect_response=False)
        login.assert_called_once_with("operador", "clave")
        session = self.client.session
        self.assertEqual(session["mikrotik_api_token"], "token-obtenido")
        self.assertEqual(session["mikrotik_api_role"], "Administrador")

    def test_logout_clears_api_session(self):
        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("mikrotik_api_token", self.client.session)

    @patch(
        "mikrotik_web_app.views.MikrotikAPIClient.get_list",
        return_value=[],
    )
    @patch(
        "mikrotik_web_app.views.MikrotikAPIClient.get",
        side_effect=APIError("La sesión de la API expiró.", status_code=401),
    )
    def test_expired_api_token_is_cleared(self, get, get_list):
        response = self.client.get(reverse("dashboard_index"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("mikrotik_api_token", self.client.session)

    @patch(
        "mikrotik_web_app.views.MikrotikAPIClient.get_list",
        return_value=[],
    )
    @patch(
        "mikrotik_web_app.views.MikrotikAPIClient.get",
        side_effect=APIError("No tiene permisos para consultar el recurso.", status_code=403),
    )
    def test_forbidden_api_response_keeps_session(self, get, get_list):
        response = self.client.get(reverse("dashboard_index"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("mikrotik_api_token", self.client.session)

    @patch("mikrotik_web_app.views.MikrotikAPIClient.get_list", return_value=[{
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

    @patch("mikrotik_web_app.views.MikrotikAPIClient.post")
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

    @patch("mikrotik_web_app.views.MikrotikAPIClient.get_list", return_value=[])
    @patch("mikrotik_web_app.views.MikrotikAPIClient.get")
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

    @patch("mikrotik_web_app.views.MikrotikAPIClient.patch")
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

    @patch("mikrotik_web_app.views.MikrotikAPIClient.post")
    def test_repair_client_red_queue(self, post):
        response = self.client.post(reverse("cliente_red_reparar_cola", args=[12]))

        self.assertRedirects(response, reverse("clientes_red_list"), fetch_redirect_response=False)
        post.assert_called_once_with("clientes-red/12/crear-cola/")

    @patch("mikrotik_web_app.views.MikrotikAPIClient.delete")
    def test_delete_client_red(self, delete):
        response = self.client.post(reverse("cliente_red_eliminar", args=[12]))

        self.assertRedirects(response, reverse("clientes_red_list"), fetch_redirect_response=False)
        delete.assert_called_once_with("clientes-red/12/")

    @patch(
        "mikrotik_web_app.views.MikrotikAPIClient.get_list",
        side_effect=[
            [{
                "id": 21,
                "cliente": 7,
                "cliente_nombre": "Cliente Factura",
                "periodo": "2026-10-01",
                "monto": "500.00",
                "fecha_vencimiento": "2026-11-05",
                "estado": "pendiente",
            }],
            [{"id": 31, "factura": 21, "monto": "200.00", "metodo": "efectivo"}],
        ],
    )
    def test_invoices_page_reads_payments_and_calculates_balance(self, get_list):
        response = self.client.get(reverse("facturas_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente Factura")
        self.assertContains(response, "300.00")
        self.assertEqual(get_list.call_args_list[0].args[0], "facturas/")
        self.assertEqual(get_list.call_args_list[1].args[0], "pagos/")

    @patch(
        "mikrotik_web_app.views.MikrotikAPIClient.get_list",
        return_value=[{
            "id": 7,
            "nombre_completo": "Cliente Factura",
        }],
    )
    def test_invoice_create_page_loads_pppoe_clients(self, get_list):
        response = self.client.get(reverse("factura_crear"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente Factura")
        get_list.assert_called_once_with("clientes-pppoe/")

    @patch("mikrotik_web_app.views.MikrotikAPIClient.post")
    def test_create_invoice(self, post):
        response = self.client.post(
            reverse("factura_crear"),
            {
                "cliente": "7",
                "periodo": "2026-11-18",
                "monto": "500.00",
                "fecha_vencimiento": "2026-12-05",
                "estado": "pendiente",
                "observaciones": "Factura mensual",
            },
        )

        self.assertRedirects(response, reverse("facturas_list"), fetch_redirect_response=False)
        post.assert_called_once_with(
            "facturas/",
            {
                "cliente": 7,
                "periodo": "2026-11-01",
                "monto": "500.00",
                "fecha_vencimiento": "2026-12-05",
                "estado": "pendiente",
                "observaciones": "Factura mensual",
            },
        )

    @patch("mikrotik_web_app.views.MikrotikAPIClient.get_list", return_value=[{
        "id": 7,
        "nombre_completo": "Cliente Factura",
    }])
    @patch("mikrotik_web_app.views.MikrotikAPIClient.get")
    def test_edit_invoice_page(self, get, get_list):
        get.return_value = {
            "id": 21,
            "cliente": 7,
            "periodo": "2026-11-01",
            "monto": "500.00",
            "fecha_vencimiento": "2026-12-05",
            "estado": "pendiente",
            "observaciones": "Factura mensual",
        }

        response = self.client.get(reverse("factura_editar", args=[21]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Editar factura")
        get.assert_called_once_with("facturas/21/")

    @patch("mikrotik_web_app.views.MikrotikAPIClient.patch")
    def test_edit_invoice_action(self, patch_client):
        response = self.client.post(
            reverse("factura_editar", args=[21]),
            {
                "cliente": "7",
                "periodo": "2026-11-01",
                "monto": "550.00",
                "fecha_vencimiento": "2026-12-05",
                "estado": "vencida",
                "observaciones": "Actualizada",
            },
        )

        self.assertRedirects(response, reverse("facturas_list"), fetch_redirect_response=False)
        patch_client.assert_called_once_with(
            "facturas/21/",
            {
                "cliente": 7,
                "periodo": "2026-11-01",
                "monto": "550.00",
                "fecha_vencimiento": "2026-12-05",
                "estado": "vencida",
                "observaciones": "Actualizada",
            },
        )

    @patch("mikrotik_web_app.views.MikrotikAPIClient.delete")
    def test_delete_invoice(self, delete):
        response = self.client.post(reverse("factura_eliminar", args=[21]))

        self.assertRedirects(response, reverse("facturas_list"), fetch_redirect_response=False)
        delete.assert_called_once_with("facturas/21/")

    @patch(
        "mikrotik_web_app.views.MikrotikAPIClient.get_list",
        side_effect=[
            [{
                "id": 31,
                "factura": 21,
                "monto": "200.00",
                "metodo": "transferencia",
                "referencia": "OP-123",
            }],
            [{
                "id": 21,
                "cliente_nombre": "Cliente Factura",
            }],
        ],
    )
    def test_payments_page_reads_api_collections(self, get_list):
        response = self.client.get(reverse("pagos_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "OP-123")
        self.assertContains(response, "Factura #21 - Cliente Factura")

    @patch(
        "mikrotik_web_app.views.MikrotikAPIClient.get_list",
        return_value=[{
            "id": 21,
            "cliente_nombre": "Cliente Factura",
        }],
    )
    def test_payment_create_page_loads_invoices(self, get_list):
        response = self.client.get(f"{reverse('pago_crear')}?factura=21")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Factura #21 - Cliente Factura")
        get_list.assert_called_once_with("facturas/")

    @patch("mikrotik_web_app.views.MikrotikAPIClient.post")
    def test_create_payment(self, post):
        response = self.client.post(
            reverse("pago_crear"),
            {
                "factura": "21",
                "monto": "200.00",
                "metodo": "transferencia",
                "referencia": "OP-123",
            },
        )

        self.assertRedirects(response, reverse("pagos_list"), fetch_redirect_response=False)
        post.assert_called_once_with(
            "pagos/",
            {
                "factura": 21,
                "monto": "200.00",
                "metodo": "transferencia",
                "referencia": "OP-123",
            },
        )

    @patch("mikrotik_web_app.views.MikrotikAPIClient.get_list", return_value=[{
        "id": 21,
        "cliente_nombre": "Cliente Factura",
    }])
    @patch("mikrotik_web_app.views.MikrotikAPIClient.get")
    def test_edit_payment_page(self, get, get_list):
        get.return_value = {
            "id": 31,
            "factura": 21,
            "monto": "200.00",
            "metodo": "transferencia",
            "referencia": "OP-123",
        }

        response = self.client.get(reverse("pago_editar", args=[31]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Editar pago")
        get.assert_called_once_with("pagos/31/")

    @patch("mikrotik_web_app.views.MikrotikAPIClient.patch")
    def test_edit_payment_action(self, patch_client):
        response = self.client.post(
            reverse("pago_editar", args=[31]),
            {
                "factura": "21",
                "monto": "250.00",
                "metodo": "efectivo",
                "referencia": "REC-456",
            },
        )

        self.assertRedirects(response, reverse("pagos_list"), fetch_redirect_response=False)
        patch_client.assert_called_once_with(
            "pagos/31/",
            {
                "factura": 21,
                "monto": "250.00",
                "metodo": "efectivo",
                "referencia": "REC-456",
            },
        )

    @patch("mikrotik_web_app.views.MikrotikAPIClient.delete")
    def test_delete_payment(self, delete):
        response = self.client.post(reverse("pago_eliminar", args=[31]))

        self.assertRedirects(response, reverse("pagos_list"), fetch_redirect_response=False)
        delete.assert_called_once_with("pagos/31/")


@override_settings(
    MIKROTIK_API_URL="http://api.test/api",
    MIKROTIK_API_TIMEOUT=5,
)
class APIClientTestCase(TestCase):
    @override_settings(
        MIKROTIK_API_TOKEN="token-directo",
        MIKROTIK_API_USERNAME="",
        MIKROTIK_API_PASSWORD="",
    )
    @patch("mikrotik_web_app.api_client.requests.request")
    def test_token_uses_drf_authorization_scheme(self, request_mock):
        response = Mock(status_code=200)
        response.json.return_value={"id": 1}
        request_mock.return_value = response

        client = MikrotikAPIClient()
        client.get("routers/1/")

        request_mock.assert_called_once_with(
            "GET",
            "http://api.test/api/routers/1/",
            headers={
                "Accept": "application/json",
                "Authorization": "Token token-directo",
            },
            timeout=5,
        )

    @override_settings(
        MIKROTIK_API_TOKEN="",
        MIKROTIK_API_USERNAME="operador",
        MIKROTIK_API_PASSWORD="clave",
    )
    @patch("mikrotik_web_app.api_client.requests.request")
    def test_credentials_request_token_before_api_call(self, request_mock):
        login_response = Mock(status_code=200)
        login_response.json.return_value={"token": "token-obtenido"}
        api_response = Mock(status_code=200)
        api_response.json.return_value={"id": 1}
        request_mock.side_effect = [login_response, api_response]

        client = MikrotikAPIClient()
        client.get("routers/1/")

        login_call, api_call = request_mock.call_args_list
        self.assertEqual(login_call.args[:2], ("POST", "http://api.test/api/token/"))
        self.assertEqual(
            login_call.kwargs["json"],
            {"username": "operador", "password": "clave"},
        )
        self.assertEqual(api_call.kwargs["headers"]["Authorization"], "Token token-obtenido")

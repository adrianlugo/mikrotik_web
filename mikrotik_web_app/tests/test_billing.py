from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.test.client import Client

class BillingViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        session = self.client.session
        session["mikrotik_api_token"] = "token-de-prueba"
        session["mikrotik_api_username"] = "operador"
        session.save()

    @patch(
        "mikrotik_web_app.api_client.MikrotikAPIClient.get_list",
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
        "mikrotik_web_app.api_client.MikrotikAPIClient.get_list",
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

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
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

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", return_value=[{
        "id": 7,
        "nombre_completo": "Cliente Factura",
    }])
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get")
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

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.patch")
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

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.delete")
    def test_delete_invoice(self, delete):
        response = self.client.post(reverse("factura_eliminar", args=[21]))

        self.assertRedirects(response, reverse("facturas_list"), fetch_redirect_response=False)
        delete.assert_called_once_with("facturas/21/")

    @patch(
        "mikrotik_web_app.api_client.MikrotikAPIClient.get_list",
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
        "mikrotik_web_app.api_client.MikrotikAPIClient.get_list",
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

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
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

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", return_value=[{
        "id": 21,
        "cliente_nombre": "Cliente Factura",
    }])
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get")
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

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.patch")
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

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.delete")
    def test_delete_payment(self, delete):
        response = self.client.post(reverse("pago_eliminar", args=[31]))

        self.assertRedirects(response, reverse("pagos_list"), fetch_redirect_response=False)
        delete.assert_called_once_with("pagos/31/")
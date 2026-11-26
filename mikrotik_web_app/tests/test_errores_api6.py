"""Tests de alineación con el formato de errores de la API (su PR #6).

La API ya no devuelve errores en varios formatos: todos usan

    {"error": "<mensaje claro en español>", "codigo": "<clave>"}

y los 400 además "detalles" (por campo o lista). Lo que se comprueba
aquí:
- La web muestra solo "error": la "codigo" nunca sale en el mensaje.
- Los "detalles" de un 400 dicen qué campo corregir.
- Un 409 es borrado protegido y un 429 son demasiadas peticiones.
- Reparar colas a medias ("partial") avisa, no se da por hecho.
"""

from unittest.mock import Mock, patch

from django.contrib.messages import get_messages
from django.test import TestCase, override_settings
from django.test.client import Client
from django.urls import reverse

from mikrotik_web_app.api_client import APIError, MikrotikAPIClient
from mikrotik_web_app.errores import mensaje_usuario


@override_settings(
    MIKROTIK_API_URL="http://api.test/api",
    MIKROTIK_API_TIMEOUT=5,
    MIKROTIK_API_TOKEN="token-de-prueba",
    MIKROTIK_API_USERNAME="",
    MIKROTIK_API_PASSWORD="",
)
class FormatoNuevoAPITestCase(TestCase):
    @patch("mikrotik_web_app.api_client.requests.request")
    def test_error_nuevo_muestra_solo_error_sin_codigo(self, request_mock):
        response = Mock(status_code=502)
        response.json.return_value = {
            "error": "El router no responde a tiempo.",
            "codigo": "router_sin_respuesta",
        }
        request_mock.return_value = response

        with self.assertRaises(APIError) as ctx:
            MikrotikAPIClient().get("routers/1/estado/")

        self.assertEqual(ctx.exception.status_code, 502)
        self.assertEqual(str(ctx.exception), "El router no responde a tiempo.")
        self.assertEqual(ctx.exception.codigo, "router_sin_respuesta")
        self.assertNotIn("codigo", str(ctx.exception))
        self.assertNotIn("router_sin_respuesta", str(ctx.exception))

    @patch("mikrotik_web_app.api_client.requests.request")
    def test_400_detalles_por_campo_dicen_que_corregir(self, request_mock):
        response = Mock(status_code=400)
        response.json.return_value = {
            "error": "subida_mbps: El valor debe ser mayor o igual que 0.",
            "codigo": "validacion",
            "detalles": {
                "subida_mbps": ["Ensure this value is greater than or equal to 0."],
                "bajada_mbps": ["Ensure this value is greater than or equal to 0."],
            },
        }
        request_mock.return_value = response

        with self.assertRaises(APIError) as ctx:
            MikrotikAPIClient().post("planes/", {})

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.codigo, "validacion")
        self.assertEqual(
            ctx.exception.detalles,
            [
                "subida_mbps: El valor debe ser mayor o igual que 0.",
                "bajada_mbps: El valor debe ser mayor o igual que 0.",
            ],
        )
        self.assertNotIn("codigo", str(ctx.exception))
        # El mensaje al usuario añade el otro campo (el primero ya viene
        # en "error") para decir qué corregir, sin repetirlo.
        texto = mensaje_usuario(ctx.exception)
        self.assertIn("bajada_mbps", texto)
        self.assertNotIn("codigo", texto)
        self.assertNotIn("Ensure this value", texto)

    @patch("mikrotik_web_app.api_client.requests.request")
    def test_400_detalles_como_lista(self, request_mock):
        response = Mock(status_code=400)
        response.json.return_value = {
            "error": "Los datos enviados no son válidos.",
            "codigo": "validacion",
            "detalles": ["subida_mbps: El valor debe ser mayor o igual que 0."],
        }
        request_mock.return_value = response

        with self.assertRaises(APIError) as ctx:
            MikrotikAPIClient().post("planes/", {})

        self.assertEqual(
            ctx.exception.detalles,
            ["subida_mbps: El valor debe ser mayor o igual que 0."],
        )
        self.assertIn("subida_mbps", mensaje_usuario(ctx.exception))

    @patch("mikrotik_web_app.api_client.requests.request")
    def test_formato_viejo_sigue_funcionando(self, request_mock):
        response = Mock(status_code=404)
        response.json.return_value = {"detail": "Not found."}
        request_mock.return_value = response

        with self.assertRaises(APIError) as ctx:
            MikrotikAPIClient().get("routers/99/")

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(str(ctx.exception), "Not found.")
        self.assertIsNone(ctx.exception.codigo)
        self.assertEqual(ctx.exception.detalles, [])

    def test_409_es_borrado_protegido(self):
        texto = mensaje_usuario(
            APIError(
                "No se puede eliminar porque hay registros que dependen de él.",
                status_code=409,
                codigo="borrado_protegido",
            )
        )
        self.assertIn("dependen", texto)

    def test_429_son_demasiadas_peticiones(self):
        texto = mensaje_usuario(
            APIError(
                "Demasiadas peticiones. Espera 30 segundos e inténtalo de nuevo.",
                status_code=429,
                codigo="demasiadas_peticiones",
            )
        )
        self.assertIn("Demasiadas peticiones", texto)
        self.assertIn("30", texto)


class RepararColasParcialTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        session = self.client.session
        session["mikrotik_api_token"] = "token-de-prueba"
        session.save()

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
    def test_reparar_colas_partial_avisa_no_es_exito(self, post_mock):
        post_mock.return_value = {
            "status": "partial",
            "colas_creadas": 1,
            "colas_actualizadas": 0,
            "total_clientes": 2,
            "errores": [
                {
                    "cliente": 5,
                    "nombre": "Cliente Oficina",
                    "mensaje": "No se pudo reparar la cola del cliente en el router.",
                }
            ],
        }

        response = self.client.post(reverse("router_reparar_colas", args=[4]))

        self.assertRedirects(
            response, reverse("router_detalle", args=[4]), fetch_redirect_response=False
        )
        mensajes = [str(m) for m in get_messages(response.wsgi_request)]
        texto = " ".join(mensajes)
        self.assertIn("en parte", texto)
        self.assertIn("Cliente Oficina", texto)
        self.assertIn("1 de 2", texto)
        self.assertNotIn("Colas DHCP/IP fija reparadas.", texto)

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
    def test_reparar_colas_success_sigue_siendo_exito(self, post_mock):
        post_mock.return_value = {
            "status": "success",
            "colas_creadas": 2,
            "colas_actualizadas": 0,
            "total_clientes": 2,
            "errores": [],
        }

        response = self.client.post(reverse("router_reparar_colas", args=[4]))

        self.assertRedirects(
            response, reverse("router_detalle", args=[4]), fetch_redirect_response=False
        )
        mensajes = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertIn("Colas DHCP/IP fija reparadas.", mensajes)

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
    def test_reparar_colas_todas_fallan_es_error_502(self, post_mock):
        post_mock.side_effect = APIError(
            "La API no pudo hablar con el router.",
            status_code=502,
            codigo="mikrotik_error",
        )

        response = self.client.post(reverse("router_reparar_colas", args=[4]))

        self.assertRedirects(
            response, reverse("router_detalle", args=[4]), fetch_redirect_response=False
        )
        mensajes = [str(m) for m in get_messages(response.wsgi_request)]
        texto = " ".join(mensajes)
        self.assertIn("router", texto)
        self.assertNotIn("Colas DHCP/IP fija reparadas.", texto)

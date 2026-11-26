"""Tests de manejo de errores: lo que ve el usuario cuando algo falla.

Reglas que se comprueban aquí:
- La API caída o el router sin respuesta se muestran en español llano,
  sin exponer texto técnico (ni inglés, ni host/puertos, ni trazas).
- El token expirado (401) limpia la sesión y redirige a login con un
  mensaje claro, en vez de dejar la página con listas vacías.
- Un 404 dice que eso ya no existe; un 403 no cierra la sesión.
- Los formularios conservan los datos enviados cuando fallan.
- Las páginas 404/500 son amigables, no la página técnica de Django.
"""

from unittest.mock import Mock, patch

import requests
from django.contrib.messages import get_messages
from django.template import loader
from django.test import TestCase, override_settings
from django.urls import reverse
from django.test.client import Client

from mikrotik_web_app.api_client import APIError, MikrotikAPIClient
from mikrotik_web_app.errores import mensaje_usuario


@override_settings(
    MIKROTIK_API_URL="http://api.test/api",
    MIKROTIK_API_TIMEOUT=5,
    MIKROTIK_API_TOKEN="token-directo",
    MIKROTIK_API_USERNAME="",
    MIKROTIK_API_PASSWORD="",
)
class ClienteErroresTestCase(TestCase):
    @patch("mikrotik_web_app.api_client.requests.request")
    def test_api_caida_no_expone_detalle_tecnico(self, request_mock):
        request_mock.side_effect = requests.ConnectionError(
            "HTTPConnectionPool(host='127.0.0.1', port=8000): Max retries "
            "exceeded with url: /api/routers/ [Errno 111] Connection refused"
        )

        with self.assertRaises(APIError) as ctx:
            MikrotikAPIClient().get("routers/")

        self.assertIsNone(ctx.exception.status_code)
        self.assertEqual(str(ctx.exception), "No se pudo conectar con la API.")
        self.assertNotIn("Connection refused", str(ctx.exception))
        self.assertNotIn("Errno", str(ctx.exception))
        self.assertNotIn("127.0.0.1", str(ctx.exception))

    @patch("mikrotik_web_app.api_client.requests.request")
    def test_error_400_traduce_mensajes_drf(self, request_mock):
        response = Mock(status_code=400)
        response.json.return_value = {"nombre_perfil": ["This field is required."]}
        request_mock.return_value = response

        with self.assertRaises(APIError) as ctx:
            MikrotikAPIClient().get("planes/")

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Este campo es obligatorio.", str(ctx.exception))
        self.assertNotIn("This field is required.", str(ctx.exception))

    @patch("mikrotik_web_app.api_client.requests.request")
    def test_error_login_aplana_el_dict_de_drf(self, request_mock):
        response = Mock(status_code=400)
        response.json.return_value = {
            "non_field_errors": ["Unable to log in with provided credentials."]
        }
        request_mock.return_value = response

        with self.assertRaises(APIError) as ctx:
            MikrotikAPIClient().login("operador", "clave-mala")

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(str(ctx.exception), "El usuario o la contraseña son incorrectos.")
        self.assertNotIn("{", str(ctx.exception))


class MensajeUsuarioTestCase(TestCase):
    def test_mapeo_por_codigo(self):
        self.assertEqual(
            mensaje_usuario(APIError("Token inválido.", status_code=401)),
            "Tu sesión caducó. Inicia sesión de nuevo.",
        )
        self.assertIn(
            "permiso",
            mensaje_usuario(APIError("Forbidden.", status_code=403)),
        )
        self.assertIn(
            "ya no existe",
            mensaje_usuario(APIError("Not found.", status_code=404)),
        )
        self.assertIn(
            "router",
            mensaje_usuario(APIError("El router no responde.", status_code=502)),
        )
        self.assertIn(
            "router",
            mensaje_usuario(APIError("Bad Gateway.", status_code=503)),
        )
        self.assertEqual(
            mensaje_usuario(APIError("No se pudo conectar con la API.")),
            "No se pudo conectar con la API. Revisa que la API esté corriendo e inténtalo de nuevo.",
        )
        self.assertEqual(
            mensaje_usuario(APIError("La API devolvió un error.", status_code=500)),
            "La API devolvió un error. Inténtalo de nuevo en unos minutos.",
        )
        # Un error que no es de la API no muestra su texto interno.
        self.assertEqual(
            mensaje_usuario(KeyError("plan")),
            "Ocurrió un error inesperado. Inténtalo de nuevo y, si sigue pasando, revisa el registro (logs/django.log).",
        )


class VistasErroresTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        session = self.client.session
        session["mikrotik_api_token"] = "token-de-prueba"
        session["mikrotik_api_username"] = "operador"
        session.save()

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get")
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", return_value=[])
    def test_token_expirado_redirige_a_login(self, get_list, get):
        get.side_effect = APIError("Token inválido.", status_code=401)

        response = self.client.get(reverse("dashboard_index"))

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("mikrotik_api_token", self.client.session)
        mensajes = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertIn("Tu sesión caducó. Inicia sesión de nuevo.", mensajes)

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get")
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", return_value=[])
    def test_403_mantiene_sesion_y_mensaje_llano(self, get_list, get):
        get.side_effect = APIError("Forbidden.", status_code=403)

        response = self.client.get(reverse("dashboard_index"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("mikrotik_api_token", self.client.session)
        self.assertContains(response, "No tienes permiso para hacer eso.")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get")
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list")
    def test_dashboard_sin_listas_muestra_guion_no_cero(self, get_list, get):
        get.return_value = {"routers": ["CHR Principal"], "total_conectados": 1, "conexiones": []}
        get_list.side_effect = [
            APIError("El router no responde.", status_code=502),
            APIError("El router no responde.", status_code=502),
            APIError("El router no responde.", status_code=502),
        ]

        response = self.client.get(reverse("dashboard_index"))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["total_clientes"])
        self.assertIsNone(response.context["total_plan_count"])
        self.assertIsNone(response.context["total_router_count"])
        self.assertContains(response, "No se pudo consultar")
        self.assertNotContains(response, "El router no responde.")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list")
    def test_lista_routers_api_caida_no_dice_no_hay(self, get_list):
        get_list.side_effect = APIError("El router no responde.", status_code=502)

        response = self.client.get(reverse("routers_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No se pudieron consultar los routers")
        self.assertNotContains(response, "No se encontraron routers registrados")
        self.assertNotContains(response, "El router no responde.")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get")
    def test_editar_cliente_404_mensaje_llano(self, get):
        get.side_effect = APIError("Not found.", status_code=404)

        response = self.client.get(reverse("cliente_editar", args=[9]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ya no existe en la API")
        self.assertNotContains(response, "Not found.")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.patch")
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list")
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get")
    def test_editar_cliente_datos_invalidos_conserva_datos(self, get, get_list, patch_client):
        cliente = {
            "id": 1,
            "nombre_completo": "Cliente Viejo",
            "usuario_pppoe": "clienteviejo",
            "direccion_ip_antena": "",
            "estado": "activo",
            "plan": 2,
            "router": 3,
        }
        get.return_value = cliente
        get_list.side_effect = lambda path: (
            [{"id": 2, "nombre_perfil": "Plan 10M", "router": 3}]
            if "planes" in path
            else [{"id": 3, "nombre": "CHR", "ip_address": "192.168.88.1"}]
        )

        response = self.client.post(
            reverse("cliente_editar", args=[1]),
            {
                "nombre_completo": "Cliente Prueba",
                "usuario_pppoe": "MALO!",
                "direccion_ip_antena": "",
                "estado": "activo",
                "plan": "2",
                "router": "3",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente Prueba")
        patch_client.assert_not_called()

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list", return_value=[])
    def test_crear_cliente_red_sin_plan_conserva_datos(self, get_list, post):
        response = self.client.post(
            reverse("cliente_red_crear"),
            {
                "nombre": "Cliente Oficina",
                "tipo": "dhcp",
                "direccion_ip": "192.168.88.51",
                "direccion_mac": "AA:BB:CC:DD:EE:01",
                "interfaz_mikrotik": "bridge-lan",
                "servidor_dhcp": "dhcp1",
                "estado": "activo",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente Oficina")
        self.assertContains(response, "Seleccione un plan y un router válidos.")
        post.assert_not_called()

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get", return_value={})
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list")
    def test_crear_plan_velocidad_no_numerica(self, get_list, get, post):
        get_list.return_value = [
            {"id": 4, "nombre": "CHR Principal", "ip_address": "192.168.88.1"}
        ]

        response = self.client.post(
            reverse("plan_crear"),
            {
                "nombre_perfil": "Plan 10M",
                "cola_padre": "",
                "direccion_local": "",
                "pool_remoto": "",
                "subida_mbps": "abc",
                "bajada_mbps": "10",
                "router": "4",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "velocidad de subida válida")
        self.assertContains(response, "Plan 10M")
        post.assert_not_called()

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post")
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list")
    def test_crear_factura_monto_no_numerico(self, get_list, post):
        get_list.return_value = [{"id": 7, "nombre_completo": "Cliente Factura"}]

        response = self.client.post(
            reverse("factura_crear"),
            {
                "cliente": "7",
                "periodo": "2026-11-01",
                "monto": "abc",
                "fecha_vencimiento": "2026-12-05",
                "estado": "pendiente",
                "observaciones": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ingrese un monto válido.")
        post.assert_not_called()

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get_list")
    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.get")
    def test_catalogo_404_dice_endpoint_no_existe(self, get, get_list):
        get_list.return_value = [
            {"id": 4, "nombre": "CHR Principal", "ip_address": "192.168.88.1"}
        ]

        def _get(path):
            if path.endswith("/colas/"):
                raise APIError("Not found.", status_code=404)
            if "direcciones-ip" in path:
                return {"direcciones": []}
            if path.endswith("/pools/"):
                return {"pools": []}
            return {}

        get.side_effect = _get

        response = self.client.get(reverse("plan_crear"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "el endpoint no existe en esta versión de la API")
        self.assertNotContains(response, "Not found.")

    def test_paginas_404_y_500_amigables(self):
        pagina_404 = loader.get_template("404.html").render({})
        self.assertIn("Página no encontrada", pagina_404)
        self.assertIn("Volver al inicio", pagina_404)
        pagina_500 = loader.get_template("500.html").render({})
        self.assertIn("Algo salió mal", pagina_500)
        self.assertIn("Volver al inicio", pagina_500)

    @override_settings(DEBUG=False)
    def test_url_inexistente_muestra_404_amigable(self):
        response = self.client.get("/web/no-existe/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Página no encontrada", status_code=404)


class LoginErroresTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.login")
    def test_login_400_son_credenciales_incorrectas(self, login_mock):
        login_mock.side_effect = APIError(
            "El usuario o la contraseña son incorrectos.", status_code=400
        )

        response = self.client.post(
            reverse("login"), {"username": "operador", "password": "mala"}
        )

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        mensajes = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertIn("El usuario o la contraseña son incorrectos.", mensajes)

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.login")
    def test_login_api_caida_no_dice_credenciales(self, login_mock):
        login_mock.side_effect = APIError("No se pudo conectar con la API.")

        response = self.client.post(
            reverse("login"), {"username": "operador", "password": "clave"}
        )

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        mensajes = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertIn("No se pudo conectar con la API.", " ".join(mensajes))
        self.assertNotIn("incorrectos", " ".join(mensajes))

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.login")
    def test_login_error_500_no_dice_credenciales_ni_conexion(self, login_mock):
        login_mock.side_effect = APIError("La API devolvió un error.", status_code=500)

        response = self.client.post(
            reverse("login"), {"username": "operador", "password": "clave"}
        )

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        mensajes = [str(m) for m in get_messages(response.wsgi_request)]
        texto = " ".join(mensajes)
        self.assertIn("La API devolvió un error.", texto)
        self.assertNotIn("incorrectos", texto)
        self.assertNotIn("No se pudo conectar", texto)

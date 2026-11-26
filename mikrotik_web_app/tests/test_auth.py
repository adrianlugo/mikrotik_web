from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.test.client import Client
from mikrotik_web_app.api_client import APIError

class AuthViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_login_view_get(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.login")
    def test_login_stores_api_token_and_role(self, login_mock):
        session = self.client.session
        session.pop("mikrotik_api_token", None)
        session.pop("mikrotik_api_username", None)
        session.save()
        login_mock.return_value = {
            "token": "token-obtenido",
            "username": "operador",
            "rol": "Administrador",
        }

        response = self.client.post(
            reverse("login"),
            {"username": "operador", "password": "clave"},
        )

        self.assertRedirects(response, reverse("dashboard_index"), fetch_redirect_response=False)
        login_mock.assert_called_once_with("operador", "clave")
        session = self.client.session
        self.assertEqual(session["mikrotik_api_token"], "token-obtenido")
        self.assertEqual(session["mikrotik_api_role"], "Administrador")

    def test_logout_clears_api_session(self):
        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("mikrotik_api_token", self.client.session)

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post", return_value={})
    def test_logout_revokes_token_when_api_allows_it(self, post):
        session = self.client.session
        session["mikrotik_api_token"] = "token-de-prueba"
        session.save()

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("mikrotik_api_token", self.client.session)
        post.assert_called_once_with("token/revocar/")

    @patch("mikrotik_web_app.api_client.MikrotikAPIClient.post", side_effect=APIError("No encontrado.", status_code=404))
    def test_logout_still_clears_session_when_api_has_no_revoke_endpoint(self, post):
        # La API responde 404 en las rutas candidatas (por ejemplo, una
        # API anterior a POST /api/token/revocar/): el cierre de sesión
        # local no debe fallar por eso.
        session = self.client.session
        session["mikrotik_api_token"] = "token-de-prueba"
        session.save()

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("mikrotik_api_token", self.client.session)
        self.assertEqual(
            [call.args[0] for call in post.call_args_list],
            ["token/revocar/", "logout/"],
        )

    def test_dashboard_redirects_to_login_without_session(self):
        self.client.cookies.clear()
        self.client.session.flush()

        response = self.client.get(reverse("dashboard_index"))

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
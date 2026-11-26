from unittest.mock import Mock, patch
from django.test import TestCase, override_settings
from mikrotik_web_app.api_client import MikrotikAPIClient

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
    def test_revoke_token_posts_to_revocar_endpoint(self, request_mock):
        response = Mock(status_code=200)
        response.json.return_value = {}
        request_mock.return_value = response

        client = MikrotikAPIClient()
        self.assertTrue(client.revocar_token())

        request_mock.assert_called_once_with(
            "POST",
            "http://api.test/api/token/revocar/",
            headers={
                "Accept": "application/json",
                "Authorization": "Token token-directo",
            },
            timeout=5,
            json={},
        )

    @override_settings(
        MIKROTIK_API_TOKEN="token-directo",
        MIKROTIK_API_USERNAME="",
        MIKROTIK_API_PASSWORD="",
    )
    @patch("mikrotik_web_app.api_client.requests.request")
    def test_revoke_token_returns_false_when_api_has_no_endpoint(self, request_mock):
        response = Mock(status_code=404)
        response.json.return_value = {"detail": "No encontrado."}
        request_mock.return_value = response

        client = MikrotikAPIClient()
        self.assertFalse(client.revocar_token())

        self.assertEqual(
            [call.args[1] for call in request_mock.call_args_list],
            [
                "http://api.test/api/token/revocar/",
                "http://api.test/api/logout/",
            ],
        )

    @override_settings(
        MIKROTIK_API_TOKEN="token-directo",
        MIKROTIK_API_USERNAME="",
        MIKROTIK_API_PASSWORD="",
    )
    @patch("mikrotik_web_app.api_client.requests.request")
    def test_revoke_token_treats_unauthorized_as_revoked(self, request_mock):
        response = Mock(status_code=401)
        response.json.return_value = {"detail": "Token inválido."}
        request_mock.return_value = response

        client = MikrotikAPIClient()
        self.assertTrue(client.revocar_token())
        request_mock.assert_called_once()
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
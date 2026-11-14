"""Testes do acesso à consulta sem usar dados de clientes reais."""

import unittest
from unittest.mock import patch

with patch("client_data.load_clients", return_value={}):
    import app as portal
from test_fixture import TEST_CLIENTS, TEST_CPF, TEST_PHONE


class ConsultationTests(unittest.TestCase):
    def setUp(self):
        portal.app.config["TESTING"] = True
        self.client = portal.app.test_client()
        portal.ATTEMPTS.clear()
        self.clients = {
            "12345678901": {
                "name": "Pessoa Exemplo",
                "companies": ["Empresa A", "Empresa B"],
                "phones": ["+5511999999999"],
            }
        }
        self.clients_patch = patch.object(portal, "CLIENTS", self.clients)
        self.clients_patch.start()
        self.addCleanup(self.clients_patch.stop)

    def test_logo_is_served_at_published_page_path(self):
        response = self.client.get("/public/banco-bradesco-logo-vertical.png")
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, "image/png")
            self.assertGreater(len(response.data), 0)
        finally:
            response.close()

    def test_unknown_client_does_not_send_sms_or_reveal_data(self):
        with patch.object(portal, "twilio_verify") as verify:
            response = self.client.post(
                "/api/request-code",
                json={"cpf": "00000000000", "phone": "11999999999"},
            )
            self.assertEqual(response.status_code, 200)
            verify.assert_not_called()
            self.assertNotIn("Pessoa Exemplo", response.get_data(as_text=True))
            self.assertEqual(
                self.client.post("/api/check-code", json={"code": "123456"}).status_code,
                400,
            )

    def test_wrong_phone_does_not_send_sms(self):
        with patch.object(portal, "twilio_verify") as verify:
            self.client.post(
                "/api/request-code",
                json={"cpf": "12345678901", "phone": "11988888888"},
            )
            verify.assert_not_called()

    def test_verified_client_receives_only_public_fields(self):
        with patch.object(portal, "twilio_verify") as verify:
            verify.side_effect = [{"status": "pending"}, {"status": "approved"}]
            requested = self.client.post(
                "/api/request-code",
                json={"cpf": "123.456.789-01", "phone": "(11) 99999-9999"},
            )
            self.assertEqual(requested.status_code, 200)
            self.assertNotIn("testCode", requested.json)
            response = self.client.post("/api/check-code", json={"code": "123456"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json), {"name", "companies", "simulatedAmountCents"})
        self.assertEqual(response.json["companies"], ["Empresa A", "Empresa B"])
        self.assertGreaterEqual(response.json["simulatedAmountCents"], 120000)
        self.assertLessEqual(response.json["simulatedAmountCents"], 280000)
        self.assertEqual(self.client.post("/api/check-code", json={"code": "123456"}).status_code, 400)

    def test_local_test_mode_uses_only_synthetic_data_without_sms(self):
        with patch.object(portal, "TEST_MODE", True), patch.object(portal, "CLIENTS", TEST_CLIENTS), patch.object(portal, "twilio_verify") as verify:
            mode = self.client.get("/api/mode")
            self.assertTrue(mode.json["testMode"])
            response = self.client.post(
                "/api/request-code",
                json={"cpf": TEST_CPF, "phone": TEST_PHONE},
            )
            code = response.json["testCode"]
            self.assertEqual(len(code), 6)
            self.assertEqual(self.client.post("/api/check-code", json={"code": "11111"}).status_code, 400)
            result = self.client.post("/api/check-code", json={"code": code})
            verify.assert_not_called()

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["name"], "Pessoa de Teste")
        self.assertEqual(result.json["companies"], ["Empresa Exemplo"])

    def test_test_mode_rejects_nonlocal_requests(self):
        with patch.object(portal, "TEST_MODE", True):
            response = self.client.get("/", environ_base={"REMOTE_ADDR": "203.0.113.10"})
        self.assertEqual(response.status_code, 403)

    def test_wrong_test_credentials_return_error_instead_of_sms_prompt(self):
        with patch.object(portal, "TEST_MODE", True), patch.object(portal, "CLIENTS", TEST_CLIENTS), patch.object(portal, "twilio_verify") as verify:
            for cpf, phone in [(TEST_CPF, "11988888888"), ("12345678901", TEST_PHONE)]:
                response = self.client.post("/api/request-code", json={"cpf": cpf, "phone": phone})
                self.assertEqual(response.status_code, 400)
                self.assertIn("fictícios", response.json["error"])
                self.assertNotIn("testCode", response.json)
            verify.assert_not_called()


if __name__ == "__main__":
    unittest.main()

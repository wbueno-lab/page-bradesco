"""Verifica a inicialização com os arquivos publicados, sem dados privados."""

from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from cryptography.fernet import Fernet
from openpyxl import Workbook

from client_data import ENCRYPTED_CLIENT_DATA_FILENAME


ROOT = Path(__file__).resolve().parent
PUBLISHED_FILES = (
    "app.py",
    "client_data.py",
    "portal.js",
    "portal-de-cr-ditos-consulta-oficial (1).html",
)
PROBE = """
import json
from app import app

app.config['TESTING'] = True
client = app.test_client()
home = client.get('/')
script = client.get('/portal.js')
mode = client.get('/api/mode')
request_code = client.post('/api/request-code', json={})
check_code = client.post('/api/check-code', json={'code': '123456'})
print(json.dumps({
    'home': home.status_code,
    'html': home.mimetype,
    'script': script.status_code,
    'script_type': script.mimetype,
    'mode_status': mode.status_code,
    'mode': mode.json,
    'request_status': request_code.status_code,
    'request': request_code.json,
    'check_status': check_code.status_code,
    'check': check_code.json,
}))
"""


def copy_published_files(directory):
    for filename in PUBLISHED_FILES:
        shutil.copy2(ROOT / filename, Path(directory) / filename)


def write_encrypted_fixture(directory):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Clientes consolidados"
    sheet.append(["Agência", "Conta", "CNPJ", "Empresa", "CPF", "Nome", "Renda", "Nascimento", "Usuário", "Telefone GOV", "Final", "E-mail", "Telefone API"])
    sheet.append(["1", "2", "3", "Empresa A", "123.456.789-01", "Pessoa Exemplo", 100, None, None, "11999999999", "9999", None, None])
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    key = Fernet.generate_key()
    encrypted = Fernet(key).encrypt(stream.getvalue())
    (Path(directory) / ENCRYPTED_CLIENT_DATA_FILENAME).write_bytes(encrypted)
    return key.decode("ascii")


def run_probe(directory, **environment):
    return subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=directory,
        env={**os.environ, **environment},
        capture_output=True,
        text=True,
        timeout=30,
    )


class DeploymentTests(unittest.TestCase):
    def test_page_opens_without_private_spreadsheet_in_dev_and_production(self):
        with TemporaryDirectory(prefix="portal-deployment-") as directory:
            copy_published_files(directory)

            for environment in ("dev", "production"):
                with self.subTest(environment=environment):
                    result = run_probe(
                        directory,
                        PORTAL_TEST_MODE="0",
                        PORTAL_ENV=environment,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    response = json.loads(result.stdout)
                    self.assertEqual(response["home"], 200)
                    self.assertEqual(response["html"], "text/html")
                    self.assertEqual(response["script"], 200)
                    self.assertEqual(response["script_type"], "application/javascript")
                    self.assertEqual(response["mode_status"], 200)
                    self.assertFalse(response["mode"]["testMode"])
                    self.assertFalse(response["mode"]["consultationAvailable"])
                    for action in ("request", "check"):
                        self.assertEqual(response[f"{action}_status"], 503)
                        self.assertEqual(set(response[action]), {"error"})
                        self.assertIn("indispon", response[action]["error"])

    def test_production_enables_consultation_with_encrypted_data_and_key(self):
        with TemporaryDirectory(prefix="portal-deployment-") as directory:
            copy_published_files(directory)
            key = write_encrypted_fixture(directory)
            result = run_probe(
                directory,
                PORTAL_TEST_MODE="0",
                PORTAL_ENV="production",
                PORTAL_DATA_KEY=key,
                VERCEL="1",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        response = json.loads(result.stdout)
        self.assertEqual(response["mode_status"], 200)
        self.assertTrue(response["mode"]["consultationAvailable"])


if __name__ == "__main__":
    unittest.main()

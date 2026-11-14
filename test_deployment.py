"""Verifica a inicializacao com os arquivos publicados, sem dados privados."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


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


class DeploymentTests(unittest.TestCase):
    def test_page_opens_without_private_spreadsheet_in_dev_and_production(self):
        with TemporaryDirectory(prefix="portal-deployment-") as directory:
            for filename in PUBLISHED_FILES:
                shutil.copy2(ROOT / filename, Path(directory) / filename)

            for environment in ("dev", "production"):
                with self.subTest(environment=environment):
                    env = {**os.environ, "PORTAL_TEST_MODE": "0", "PORTAL_ENV": environment}
                    result = subprocess.run(
                        [sys.executable, "-c", PROBE],
                        cwd=directory,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=30,
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


if __name__ == "__main__":
    unittest.main()

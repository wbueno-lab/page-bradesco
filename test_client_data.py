"""Testes da leitura da planilha com registros inteiramente sintéticos."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cryptography.fernet import Fernet
from openpyxl import Workbook

from client_data import (
    ClientDataUnavailable,
    ENCRYPTED_CLIENT_DATA_FILENAME,
    load_clients,
    load_clients_for_environment,
    normalize_phone,
)


class ClientDataTests(unittest.TestCase):
    @staticmethod
    def write_workbook(path):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Clientes consolidados"
        sheet.append(["Agência", "Conta", "CNPJ", "Empresa", "CPF", "Nome", "Renda", "Nascimento", "Usuário", "Telefone GOV", "Final", "E-mail", "Telefone API"])
        sheet.append(["1", "2", "3", "Empresa A", "123.456.789-01", "Pessoa Exemplo", 100, None, None, "11999999999", "9999", None, None])
        sheet.append(["1", "2", "3", "Empresa B", "123.456.789-01", "Pessoa Exemplo", 100, None, None, None, "8888", None, "11988888888"])
        workbook.save(path)
        workbook.close()

    def test_multiple_companies_and_registered_phones(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "clientes.xlsx"
            self.write_workbook(path)
            clients = load_clients(path)

        self.assertEqual(clients["12345678901"]["companies"], ["Empresa A", "Empresa B"])
        self.assertEqual(clients["12345678901"]["phones"], ["+5511999999999", "+5511988888888"])
        self.assertNotIn("email", clients["12345678901"])
        self.assertIsNone(normalize_phone("9999"))

    def test_vercel_loads_encrypted_client_data(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            workbook_path = root / "clientes.xlsx"
            encrypted_path = root / ENCRYPTED_CLIENT_DATA_FILENAME
            self.write_workbook(workbook_path)
            key = Fernet.generate_key()
            encrypted_path.write_bytes(Fernet(key).encrypt(workbook_path.read_bytes()))

            clients = load_clients_for_environment(
                root,
                {"VERCEL": "1", "PORTAL_DATA_KEY": key.decode("ascii")},
            )

        self.assertEqual(clients["12345678901"]["name"], "Pessoa Exemplo")

    def test_vercel_rejects_encrypted_data_without_key(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ENCRYPTED_CLIENT_DATA_FILENAME).write_bytes(b"encrypted")

            with self.assertRaises(ClientDataUnavailable):
                load_clients_for_environment(root, {"VERCEL": "1"})


if __name__ == "__main__":
    unittest.main()

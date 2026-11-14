"""Testes da leitura da planilha com registros inteiramente sintéticos."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import Workbook

from client_data import load_clients, normalize_phone


class ClientDataTests(unittest.TestCase):
    def test_multiple_companies_and_registered_phones(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "clientes.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Clientes consolidados"
            sheet.append(["Agência", "Conta", "CNPJ", "Empresa", "CPF", "Nome", "Renda", "Nascimento", "Usuário", "Telefone GOV", "Final", "E-mail", "Telefone API"])
            sheet.append(["1", "2", "3", "Empresa A", "123.456.789-01", "Pessoa Exemplo", 100, None, None, "11999999999", "9999", None, None])
            sheet.append(["1", "2", "3", "Empresa B", "123.456.789-01", "Pessoa Exemplo", 100, None, None, None, "8888", None, "11988888888"])
            workbook.save(path)

            clients = load_clients(path)

        self.assertEqual(clients["12345678901"]["companies"], ["Empresa A", "Empresa B"])
        self.assertEqual(clients["12345678901"]["phones"], ["+5511999999999", "+5511988888888"])
        self.assertNotIn("email", clients["12345678901"])
        self.assertIsNone(normalize_phone("9999"))


if __name__ == "__main__":
    unittest.main()

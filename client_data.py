"""Leitura da planilha privada para consultas autorizadas por CPF."""

from collections import defaultdict
from io import BytesIO
import os
from pathlib import Path
import re

from cryptography.fernet import Fernet, InvalidToken
from openpyxl import load_workbook


PLAINTEXT_CLIENT_DATA_FILENAME = "clientes_consolidados_completo.xlsx"
ENCRYPTED_CLIENT_DATA_FILENAME = "client_data.fernet"


class ClientDataUnavailable(RuntimeError):
    """Indica que a base privada não pode ser aberta com segurança."""


def normalize_cpf(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) == 11 else None


def normalize_phone(value):
    digits = re.sub(r"\D", "", str(value or ""))
    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]
    return f"+55{digits}" if len(digits) in (10, 11) else None


def load_clients(path: Path):
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook["Clientes consolidados"]
        clients = {}
        companies_by_cpf = defaultdict(set)
        phones_by_cpf = defaultdict(set)

        for row in sheet.iter_rows(min_row=2, values_only=True):
            cpf = normalize_cpf(row[4])
            if not cpf:
                continue

            name = str(row[5] or "").strip()
            company = str(row[3] or "").strip()
            if not name:
                continue

            clients.setdefault(cpf, {"name": name, "companies": [], "phones": []})
            if company and company not in companies_by_cpf[cpf]:
                companies_by_cpf[cpf].add(company)
                clients[cpf]["companies"].append(company)
            for value in (row[9], row[12]):
                phone = normalize_phone(value)
                if phone and phone not in phones_by_cpf[cpf]:
                    phones_by_cpf[cpf].add(phone)
                    clients[cpf]["phones"].append(phone)

        return clients
    finally:
        workbook.close()


def load_clients_for_environment(root: Path, environment=None):
    """Carrega dados locais em desenvolvimento e dados criptografados na Vercel."""
    environment = os.environ if environment is None else environment
    plaintext_path = root / PLAINTEXT_CLIENT_DATA_FILENAME
    if environment.get("VERCEL") != "1" and plaintext_path.is_file():
        return load_clients(plaintext_path)

    encrypted_path = root / ENCRYPTED_CLIENT_DATA_FILENAME
    if not encrypted_path.is_file():
        raise FileNotFoundError(encrypted_path)

    key = str(environment.get("PORTAL_DATA_KEY", "")).strip()
    if not key:
        raise ClientDataUnavailable("PORTAL_DATA_KEY não configurada")

    try:
        payload = Fernet(key.encode("ascii")).decrypt(encrypted_path.read_bytes())
    except (InvalidToken, UnicodeEncodeError, ValueError) as error:
        raise ClientDataUnavailable("Base privada ou chave inválida") from error
    return load_clients(BytesIO(payload))

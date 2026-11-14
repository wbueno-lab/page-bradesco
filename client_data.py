"""Leitura da planilha privada para consultas autorizadas por CPF."""

from collections import defaultdict
from pathlib import Path
import re

from openpyxl import load_workbook


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

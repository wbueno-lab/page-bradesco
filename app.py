"""Consulta demonstrativa com verificação por SMS e planilha privada."""

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import compare_digest
import json
import os
from pathlib import Path
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import Flask, jsonify, request, send_file, session

from client_data import load_clients, normalize_cpf, normalize_phone


ROOT = Path(__file__).resolve().parent
TEST_MODE = os.environ.get("PORTAL_TEST_MODE") == "1"
if TEST_MODE and os.environ.get("PORTAL_ENV") != "test":
    raise RuntimeError("PORTAL_TEST_MODE exige PORTAL_ENV=test")
if TEST_MODE:
    from test_fixture import TEST_CLIENTS

    CLIENTS = TEST_CLIENTS
else:
    CLIENTS = load_clients(ROOT / "clientes_consolidados_completo.xlsx")
PENDING = {}
ATTEMPTS = defaultdict(deque)
app = Flask(__name__, static_folder=None)
app.secret_key = os.environ.get("PORTAL_SESSION_SECRET") or secrets.token_hex(32)
app.config.update(
    MAX_CONTENT_LENGTH=2048,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    SESSION_COOKIE_SECURE=os.environ.get("PORTAL_COOKIE_SECURE") == "1",
)


@app.before_request
def test_mode_local_only():
    if TEST_MODE and request.remote_addr not in ("127.0.0.1", "::1"):
        return jsonify(error="Modo de teste disponível apenas no computador local."), 403


@app.after_request
def private_response(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/")
def home():
    return send_file(ROOT / "portal-de-cr-ditos-consulta-oficial (1).html")


@app.get("/portal.js")
def script():
    return send_file(ROOT / "portal.js", mimetype="application/javascript")


@app.get("/api/mode")
def mode():
    if TEST_MODE:
        from test_fixture import TEST_CPF, TEST_PHONE

        return jsonify(testMode=True, testCpf=TEST_CPF, testPhone=TEST_PHONE)
    return jsonify(testMode=False)


def limited(key, maximum=5, window=3600):
    now = datetime.now(timezone.utc).timestamp()
    attempts = ATTEMPTS[key]
    while attempts and now - attempts[0] > window:
        attempts.popleft()
    if len(attempts) >= maximum:
        return True
    attempts.append(now)
    return False


def purge_expired():
    now = datetime.now(timezone.utc)
    for ticket, pending in list(PENDING.items()):
        if pending["expires"] < now:
            PENDING.pop(ticket, None)


def twilio_verify(endpoint, fields):
    service = os.environ.get("TWILIO_VERIFY_SERVICE_SID", "")
    user = os.environ.get("TWILIO_API_KEY", "")
    password = os.environ.get("TWILIO_API_SECRET", "")
    if not all((service, user, password)):
        raise RuntimeError("Twilio Verify não configurado")

    import base64

    authorization = base64.b64encode(f"{user}:{password}".encode()).decode()
    url = f"https://verify.twilio.com/v2/Services/{service}/{endpoint}"
    call = Request(
        url,
        data=urlencode(fields).encode(),
        headers={
            "Authorization": f"Basic {authorization}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urlopen(call, timeout=10) as response:
        return json.load(response)


@app.post("/api/request-code")
def request_code():
    purge_expired()
    if limited(("request", request.remote_addr)):
        return jsonify(error="Muitas tentativas. Tente novamente mais tarde."), 429

    data = request.get_json(silent=True) or {}
    cpf = normalize_cpf(data.get("cpf"))
    phone = normalize_phone(data.get("phone"))
    if not cpf or not phone:
        return jsonify(error="Informe CPF e telefone válidos."), 400

    session.clear()
    client = CLIENTS.get(cpf)
    if TEST_MODE and (not client or phone not in client["phones"]):
        return jsonify(error="No modo de teste, use o CPF e o telefone fictícios indicados na tela."), 400
    if client and phone in client["phones"]:
        test_code = str(secrets.randbelow(900000) + 100000) if TEST_MODE else None
        if not TEST_MODE:
            try:
                twilio_verify("Verifications", {"To": phone, "Channel": "sms"})
            except RuntimeError:
                return jsonify(error="O envio de SMS ainda não está configurado."), 503
            except (HTTPError, URLError, TimeoutError):
                return jsonify(error="Não foi possível enviar o SMS agora."), 503

        ticket = secrets.token_urlsafe(32)
        PENDING[ticket] = {
            "cpf": cpf,
            "phone": phone,
            "expires": datetime.now(timezone.utc) + timedelta(minutes=10),
            "test_code": test_code,
        }
        session["ticket"] = ticket
        if TEST_MODE:
            return jsonify(message="Código de teste gerado localmente. Nenhum SMS foi enviado.", testCode=test_code)

    return jsonify(message="Se o CPF e o telefone corresponderem ao cadastro, você receberá um código por SMS.")


@app.post("/api/check-code")
def check_code():
    if limited(("check", request.remote_addr), maximum=10, window=600):
        return jsonify(error="Muitas tentativas. Tente novamente mais tarde."), 429

    data = request.get_json(silent=True) or {}
    code = str(data.get("code", "")).strip()
    ticket = session.get("ticket")
    pending = PENDING.get(ticket)
    if not pending or not code.isdigit() or not 4 <= len(code) <= 10:
        return jsonify(error="Código inválido ou expirado."), 400

    if datetime.now(timezone.utc) > pending["expires"]:
        PENDING.pop(ticket, None)
        session.clear()
        return jsonify(error="Código expirado. Solicite outro SMS."), 400

    if TEST_MODE:
        approved = compare_digest(code, pending["test_code"])
    else:
        try:
            result = twilio_verify("VerificationCheck", {"To": pending["phone"], "Code": code})
        except (RuntimeError, HTTPError, URLError, TimeoutError):
            return jsonify(error="Não foi possível verificar o código agora."), 503
        approved = compare_digest(result.get("status", ""), "approved")
    if not approved:
        return jsonify(error="Código incorreto ou expirado."), 400

    PENDING.pop(ticket, None)
    session.clear()
    amount_cents = 120000 + int(sha256(pending["cpf"].encode()).hexdigest()[:8], 16) % 160001
    client = CLIENTS[pending["cpf"]]
    return jsonify(name=client["name"], companies=client["companies"], simulatedAmountCents=amount_cents)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)

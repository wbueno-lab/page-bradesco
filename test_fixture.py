"""Cadastro sintético usado exclusivamente no modo de teste local."""

TEST_CPF = "00000000000"
TEST_PHONE = "+5511999999999"
TEST_CLIENTS = {
    TEST_CPF: {
        "name": "Pessoa de Teste",
        "companies": ["Empresa Exemplo"],
        "phones": [TEST_PHONE],
    }
}

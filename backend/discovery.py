import os
import requests
from dotenv import load_dotenv
import json

# --- Configuração ---
# (Carrega .env)
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if not os.path.exists(dotenv_path):
    print("AVISO: .env não encontrado. Tentando carregar do diretório atual.")
    dotenv_path = '.env'
load_dotenv(dotenv_path)

# --- Variáveis de Teste ---
BASE_URL = "https://evolution-api-129644477821.us-central1.run.app"
API_KEY = os.getenv("EVOLUTION_API_KEY")
INSTANCE_NAME = "cosmos-test"
# Pega um JID de teste real do seu log (para o payload de findMessages)
TEST_JID = "12068996705@s.whatsapp.net"

HEADERS = {"apikey": API_KEY, "Accept": "application/json"}


# --- Classes de Cores (igual) ---
class C:
    OK = '\033[92m'
    FAIL = '\033[91m'
    WARN = '\033[93m'
    INFO = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


# --- Função de Teste (igual) ---
def test_endpoint(title: str, method: str, url: str, **kwargs):
    """
    Executa um teste em um endpoint e imprime o resultado formatado.
    Esta função NÃO É um 'pytest' test.
    """
    print(f"\n{C.BOLD}--- {title} ---{C.END}")
    print(f"Testando: {C.INFO}{method} {url}{C.END}")

    try:
        if method.upper() == "GET":
            response = requests.get(url, **kwargs)
        elif method.upper() == "POST":
            response = requests.post(url, **kwargs)
        else:
            print(f"{C.WARN}Método {method} não suportado pelo script.{C.END}")
            return

        status_color = C.OK if 200 <= response.status_code < 300 else C.FAIL
        print(f"Status: {status_color}{response.status_code}{C.END}")

        try:
            print("Response (JSON):")
            print(json.dumps(response.json(), indent=2))
        except requests.exceptions.JSONDecodeError:
            print(f"Response (Texto): {response.text[:200]}...")

    except requests.exceptions.RequestException as e:
        print(f"{C.FAIL}ERRO NA REQUISIÇÃO: {e}{C.END}")


# --- Execução dos Testes ---
if __name__ == "__main__":
    print(f"{C.BOLD}🚀 Iniciando Diagnóstico da Evolution API (v2) em:{C.END} {BASE_URL}")
    if not API_KEY:
        print(f"\n{C.FAIL}ERRO CRÍTICO: EVOLUTION_API_KEY não encontrada.{C.END}")
        exit()

    print(f"Usando JID de teste: {TEST_JID}")

    # === TESTE 1: 'findChats' (O que já funciona) ===
    # Apenas para confirmar que a API Key e a conexão estão OK.
    test_endpoint(
        "Teste 1: 'findChats' (Controle - Deve funcionar)",
        "POST", f"{BASE_URL}/chat/findChats/{INSTANCE_NAME}",
        headers=HEADERS,
        json=None
    )

    # === TESTE 2: 'findMessages' (O que falhou no log) ===
    # Esta é a minha suposição do main.py que deu 404
    test_endpoint(
        "Teste 2: 'findMessages' (Minha suposição que falhou)",
        "POST", f"{BASE_URL}/message/findMessages/{INSTANCE_NAME}",
        headers=HEADERS,
        json={"jid": TEST_JID, "page": 1, "pageSize": 5}
    )

    # === TESTE 3: Hipótese B (Endpoint 'chat/findMessages'?) ===
    # Esta é a minha suspeita mais forte, seguindo o padrão do findChats
    test_endpoint(
        "Teste 3: 'chat/findMessages' (Hipótese mais provável)",
        "POST", f"{BASE_URL}/chat/findMessages/{INSTANCE_NAME}",
        headers=HEADERS,
        json={"jid": TEST_JID, "page": 1, "pageSize": 5}
    )

    # === TESTE 4: Hipótese C (Payload 'where'?) ===
    # A doc v1 usava um 'where'
    test_endpoint(
        "Teste 4: 'chat/findMessages' (Payload alternativo?)",
        "POST", f"{BASE_URL}/chat/findMessages/{INSTANCE_NAME}",
        headers=HEADERS,
        json={"where": {"remoteJid": TEST_JID}, "limit": 5}
    )

    print(f"\n{C.BOLD}✅ Diagnóstico Concluído.{C.END}")
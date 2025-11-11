# Em backend/inspector.py
# (Novo arquivo)

import os
import json
import requests  # Usando 'requests' por ser mais simples para scripts síncronos
from dotenv import load_dotenv
from pathlib import Path

# --- Configuração ---
# Encontra o arquivo .env na pasta 'backend'
env_path = Path(__file__).parent / '.env'
if not env_path.exists():
    print(f"AVISO: .env não encontrado em {env_path}. Tentando o diretório atual.")
    env_path = '.env'

print(f"Carregando variáveis de {env_path.resolve()}")
load_dotenv(dotenv_path=env_path)

# --- Variáveis de Conexão (Puxadas do .env) ---
BASE_URL = os.getenv("EVOLUTION_API_URL", "https://evolution-api-129644477821.us-central1.run.app")
API_KEY = os.getenv("EVOLUTION_API_KEY")
INSTANCE_NAME = "cosmos-test"

if not API_KEY:
    print("\n❌ ERRO CRÍTICO: EVOLUTION_API_KEY não encontrada. Verifique seu arquivo .env")
    exit()

HEADERS = {
    "apikey": API_KEY,
    "Accept": "application/json",
    "Content-Type": "application/json"
}


# --- Classes de Cores (para facilitar a leitura) ---
class C:
    OK = '\033[92m'  # VERDE
    FAIL = '\033[91m'  # VERMELHO
    INFO = '\033[94m'  # AZUL
    BOLD = '\033[1m'
    END = '\033[0m'


def print_json(data):
    """Imprime JSON formatado com cores."""
    print(C.OK + json.dumps(data, indent=2, ensure_ascii=False) + C.END)


def fetch_endpoint(title, method, url, **kwargs):
    """Função genérica para chamar um endpoint e imprimir a resposta."""
    print("\n" + "=" * 70)
    print(f"{C.BOLD}🚀 {title} {C.END}")
    print(f"Chamando: {C.INFO}{method} {url}{C.END}")
    print("=" * 70)

    try:
        if method.upper() == 'GET':
            response = requests.get(url, **kwargs)
        elif method.upper() == 'POST':
            response = requests.post(url, **kwargs)

        response.raise_for_status()  # Levanta um erro para status 4xx/5xx

        print(f"✅ {C.OK}Status: {response.status_code}{C.END}\n")
        print("--- INÍCIO DO JSON DA RESPOSTA ---")
        print_json(response.json())
        print("--- FIM DO JSON DA RESPOSTA ---")

    except requests.exceptions.HTTPError as e:
        print(f"❌ {C.FAIL}ERRO HTTP: {e.response.status_code} {e.response.reason}{C.END}")
        try:
            print("--- INÍCIO DO JSON DE ERRO ---")
            print_json(e.response.json())
            print("--- FIM DO JSON DE ERRO ---")
        except json.JSONDecodeError:
            print(e.response.text)
    except requests.exceptions.RequestException as e:
        print(f"❌ {C.FAIL}ERRO DE CONEXÃO: {e}{C.END}")
    except json.JSONDecodeError:
        print(f"❌ {C.FAIL}ERRO: Resposta recebida não é um JSON válido.{C.END}")
        print(response.text)


# =================================================================
# EXECUÇÃO DO SCRIPT DE INSPEÇÃO
# =================================================================
if __name__ == "__main__":
    print(f"Iniciando inspeção da API Evolution em: {BASE_URL}")
    print(f"Instância: {INSTANCE_NAME}\n")

    # --- Endpoint 1: Status da Instância ---
    # (Usado pelo useAuth.js e ConnectInstancePage.js)
    fetch_endpoint(
        "JSON 1: Status da Instância (connectionState)",
        "GET",
        f"{BASE_URL}/instance/connectionState/{INSTANCE_NAME}",
        headers=HEADERS
    )

    # --- Endpoint 2: Lista de Chats (findChats) ---
    # (Usado pela Sincronização em main.py para buscar 'pushName')
    fetch_endpoint(
        "JSON 2: Lista de Chats (findChats)",
        "POST",
        f"{BASE_URL}/chat/findChats/{INSTANCE_NAME}",
        headers=HEADERS,
        json=None  # Este endpoint espera um corpo nulo
    )

    # --- Endpoint 3: Mensagens Recentes (findMessages) ---
    # (Usado pela Sincronização em main.py para buscar mensagens)
    fetch_endpoint(
        "JSON 3: Mensagens Recentes (findMessages - 10 mais recentes)",
        "POST",
        f"{BASE_URL}/chat/findMessages/{INSTANCE_NAME}",
        headers=HEADERS,
        json={
            "page": 1,
            "pageSize": 10
        }
    )

    print("\n" + "=" * 70)
    print(f"✅ {C.BOLD}Inspeção Concluída.{C.END}")
    print("=" * 70)
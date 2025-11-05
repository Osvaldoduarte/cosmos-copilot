# Em backend/core/shared.py

# --- Classes de Cores ---
class Colors:
    RED = '\033[91m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    END = '\033[0m'

# --- Funções de Impressão (Log) ---
def print_error(msg): print(f"{Colors.RED}❌ {msg}{Colors.END}")
def print_info(msg): print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")
def print_success(msg): print(f"{Colors.GREEN}✅ {msg}{Colors.END}")
def print_warning(msg): print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")

# --- Dicionário Global de IA (Registry Pattern) ---
# Armazena os modelos carregados para que os endpoints possam acessá-los.
IA_MODELS = {
    "llm": None,
    "retriever": None,
    "embeddings": None,
    "playbook": None,
    "chroma_client": None
}
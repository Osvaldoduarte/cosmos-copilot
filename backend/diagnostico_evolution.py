#!/usr/bin/env python3
"""
Script de Diagnóstico - Evolution API + Cosmos Copilot

Este script verifica a configuração e conectividade de todos os componentes.
Execute com: python diagnostico_evolution.py
"""

import os
import sys
import asyncio
import httpx
from dotenv import load_dotenv
from pathlib import Path


# Cores para output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_success(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")


def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")


def print_warning(msg):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")


def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")


def print_section(title):
    print(f"\n{Colors.BLUE}{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}{Colors.END}\n")


async def check_env_variables():
    """Verifica se as variáveis de ambiente necessárias estão configuradas."""
    print_section("1. Verificando Variáveis de Ambiente")

    required_vars = {
        "EVOLUTION_API_URL": "URL da Evolution API",
        "EVOLUTION_INSTANCE_NAME": "Nome da instância",
        "EVOLUTION_API_KEY": "Chave da API",
        "GEMINI_API_KEY": "Chave do Google Gemini",
        "WEBHOOK_URL": "URL do Webhook"
    }

    all_ok = True
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            # Mascara valores sensíveis
            if "KEY" in var or "PASSWORD" in var:
                display_value = f"{value[:10]}...{value[-4:]}" if len(value) > 14 else "***"
            else:
                display_value = value
            print_success(f"{description}: {display_value}")
        else:
            print_error(f"{description} ({var}) não configurada!")
            all_ok = False

    return all_ok


async def check_evolution_api():
    """Verifica conectividade com a Evolution API."""
    print_section("2. Verificando Conexão com Evolution API")

    url = os.getenv("EVOLUTION_API_URL")
    api_key = os.getenv("EVOLUTION_API_KEY")
    instance = os.getenv("EVOLUTION_INSTANCE_NAME")

    if not all([url, api_key, instance]):
        print_error("Variáveis de ambiente faltando!")
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Testa conexão básica
            print_info(f"Testando conexão com {url}...")
            response = await client.get(f"{url}/instance/fetchInstances",
                                        headers={"apikey": api_key})

            if response.status_code == 200:
                print_success(f"Evolution API está acessível!")

                # Lista instâncias
                instances = response.json()
                print_info(f"Instâncias encontradas: {len(instances)}")

                # Verifica se a instância configurada existe
                instance_names = [inst.get("instance", {}).get("instanceName") for inst in instances]
                if instance in instance_names:
                    print_success(f"Instância '{instance}' encontrada!")

                    # Verifica status da conexão
                    conn_response = await client.get(
                        f"{url}/instance/connectionState/{instance}",
                        headers={"apikey": api_key}
                    )

                    if conn_response.status_code == 200:
                        conn_data = conn_response.json()
                        state = conn_data.get("state")
                        if state == "open":
                            print_success(f"WhatsApp conectado! Status: {state}")
                        else:
                            print_warning(f"WhatsApp não conectado. Status: {state}")
                            print_info("Você precisa conectar o WhatsApp escaneando o QR Code.")

                    return True
                else:
                    print_error(f"Instância '{instance}' não encontrada!")
                    print_info(f"Instâncias disponíveis: {', '.join(instance_names)}")
                    return False
            else:
                print_error(f"Erro ao conectar: Status {response.status_code}")
                print_info(f"Resposta: {response.text}")
                return False

    except httpx.ConnectError:
        print_error("Não foi possível conectar à Evolution API!")
        print_info("Verifique se o Docker está rodando: docker-compose ps")
        return False
    except Exception as e:
        print_error(f"Erro inesperado: {e}")
        return False


async def check_database():
    """Verifica configuração do banco de dados."""
    print_section("3. Verificando Banco de Dados")

    db_uri = os.getenv("DATABASE_CONNECTION_URI")
    if db_uri:
        print_success(f"String de conexão configurada")

        # Testa conexão com PostgreSQL via Docker
        try:
            import subprocess
            result = subprocess.run(
                ["docker", "exec", "evolution_postgres", "pg_isready", "-U", "evolution"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                print_success("PostgreSQL está rodando e aceitando conexões!")

                # Verifica tabelas
                result = subprocess.run(
                    ["docker", "exec", "evolution_postgres", "psql", "-U", "evolution",
                     "-d", "evolution", "-c", "SELECT COUNT(*) FROM \"Message\";"],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    count = result.stdout.strip().split('\n')[2].strip()
                    print_success(f"Banco de dados operacional! {count} mensagens armazenadas.")
                else:
                    print_warning("Banco existe mas pode estar vazio ou sem as tabelas.")

                return True
            else:
                print_error("PostgreSQL não está respondendo!")
                return False

        except FileNotFoundError:
            print_warning("Docker não encontrado. Não foi possível verificar o banco.")
            return False
    else:
        print_error("DATABASE_CONNECTION_URI não configurada!")
        return False


async def check_chromadb():
    """Verifica o banco de dados vetorial ChromaDB."""
    print_section("4. Verificando ChromaDB (Base de Conhecimento)")

    chroma_path = Path(__file__).parent / "chroma_db_local"

    if chroma_path.exists():
        print_success(f"ChromaDB encontrado em: {chroma_path}")

        # Conta arquivos
        files = list(chroma_path.rglob("*"))
        print_info(f"Total de arquivos: {len(files)}")

        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(chroma_path))
            collections = client.list_collections()

            if collections:
                print_success(f"ChromaDB operacional! {len(collections)} coleção(ões) encontrada(s).")
                for col in collections:
                    count = col.count()
                    print_info(f"  - {col.name}: {count} documentos")
            else:
                print_warning("ChromaDB existe mas está vazio.")
                print_info("Execute: python scripts/gerenciar_pipeline.py")

            return True
        except Exception as e:
            print_error(f"Erro ao acessar ChromaDB: {e}")
            return False
    else:
        print_error("ChromaDB não encontrado!")
        print_info("Execute: python scripts/gerenciar_pipeline.py")
        return False


async def check_webhook():
    """Verifica configuração do webhook."""
    print_section("5. Verificando Webhook")

    webhook_url = os.getenv("WEBHOOK_URL")
    if not webhook_url:
        print_error("WEBHOOK_URL não configurada!")
        return False

    print_info(f"Webhook configurado: {webhook_url}")

    # Verifica se o backend está rodando
    backend_host = webhook_url.split("//")[1].split(":")[0]
    backend_port = webhook_url.split(":")[2].split("/")[0] if ":" in webhook_url.split("//")[1] else "80"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Tenta acessar o endpoint raiz do backend
            test_url = f"http://{backend_host}:{backend_port}/"
            response = await client.get(test_url)

            if response.status_code == 200:
                print_success("Backend está rodando e acessível!")
                return True
            else:
                print_warning(f"Backend responde mas com status: {response.status_code}")
                return False
    except httpx.ConnectError:
        print_error("Backend não está acessível!")
        print_info("Certifique-se de que o backend está rodando: uvicorn main:app --reload")
        return False
    except Exception as e:
        print_error(f"Erro ao testar webhook: {e}")
        return False


async def check_data_files():
    """Verifica arquivos de dados necessários."""
    print_section("6. Verificando Arquivos de Dados")

    base_path = Path(__file__).parent
    data_path = base_path / "data"

    required_files = {
        "playbook_vendas.json": "Playbook de vendas",
        "youtube_links.txt": "Lista de vídeos (opcional)"
    }

    all_ok = True
    for filename, description in required_files.items():
        filepath = data_path / filename
        if filepath.exists():
            size = filepath.stat().st_size
            print_success(f"{description}: {filename} ({size} bytes)")
        else:
            if filename == "youtube_links.txt":
                print_warning(f"{description} não encontrado (opcional)")
            else:
                print_error(f"{description} não encontrado: {filename}")
                all_ok = False

    # Verifica arquivos processados
    jsonl_files = list(data_path.glob("refinado_*.jsonl"))
    if jsonl_files:
        print_success(f"Base de conhecimento: {len(jsonl_files)} arquivo(s) processado(s)")
    else:
        print_warning("Nenhum arquivo de conhecimento processado encontrado")
        print_info("Execute: python scripts/gerenciar_pipeline.py")

    return all_ok


async def test_conversation_sync():
    """Testa sincronização de conversas."""
    print_section("7. Testando Sincronização de Conversas")

    url = os.getenv("EVOLUTION_API_URL")
    api_key = os.getenv("EVOLUTION_API_KEY")
    instance = os.getenv("EVOLUTION_INSTANCE_NAME")

    if not all([url, api_key, instance]):
        print_error("Configuração incompleta!")
        return False

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Busca todas as conversas
            print_info("Buscando conversas da Evolution API...")
            response = await client.get(
                f"{url}/chat/findAll/{instance}",
                headers={"apikey": api_key}
            )

            if response.status_code == 200:
                chats = response.json()
                print_success(f"Encontradas {len(chats)} conversas na Evolution API")

                if chats:
                    # Mostra detalhes da primeira conversa
                    first_chat = chats[0]
                    chat_id = first_chat.get("id")
                    print_info(f"Exemplo de conversa: {chat_id}")

                    # Testa busca de mensagens
                    msg_response = await client.get(
                        f"{url}/chat/findMessages/{instance}",
                        params={"id": chat_id, "limit": 5},
                        headers={"apikey": api_key}
                    )

                    if msg_response.status_code == 200:
                        messages = msg_response.json().get("messages", [])
                        print_success(f"Conseguiu buscar mensagens! Exemplo: {len(messages)} mensagens")
                        return True
                    else:
                        print_error(f"Erro ao buscar mensagens: {msg_response.status_code}")
                        return False
                else:
                    print_warning("Nenhuma conversa encontrada. Envie uma mensagem de teste.")
                    return True
            else:
                print_error(f"Erro ao buscar conversas: {response.status_code}")
                return False

    except Exception as e:
        print_error(f"Erro no teste de sincronização: {e}")
        return False


async def main():
    """Função principal de diagnóstico."""
    print(f"\n{Colors.BLUE}╔{'═' * 58}╗")
    print(f"║{' ' * 15}🔍 DIAGNÓSTICO DO SISTEMA{' ' * 16}║")
    print(f"║{' ' * 12}Cosmos Copilot + Evolution API{' ' * 14}║")
    print(f"╚{'═' * 58}╝{Colors.END}\n")

    # Carrega variáveis de ambiente
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        print_error(f"Arquivo .env não encontrado em: {env_path}")
        print_info("Crie o arquivo .env na raiz do projeto com as configurações necessárias.")
        sys.exit(1)

    load_dotenv(env_path)

    # Executa todas as verificações
    results = {
        "Variáveis de Ambiente": await check_env_variables(),
        "Evolution API": await check_evolution_api(),
        "Banco de Dados": await check_database(),
        "ChromaDB": await check_chromadb(),
        "Webhook": await check_webhook(),
        "Arquivos de Dados": await check_data_files(),
        "Sincronização": await test_conversation_sync()
    }

    # Resumo final
    print_section("📊 RESUMO DO DIAGNÓSTICO")

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    for check, status in results.items():
        if status:
            print_success(f"{check}: OK")
        else:
            print_error(f"{check}: FALHOU")

    print(f"\n{Colors.BLUE}{'─' * 60}{Colors.END}")
    percentage = (passed / total) * 100

    if percentage == 100:
        print(f"{Colors.GREEN}🎉 Perfeito! Todos os {total} testes passaram!{Colors.END}")
        print(f"{Colors.GREEN}Seu sistema está pronto para uso.{Colors.END}")
    elif percentage >= 70:
        print(f"{Colors.YELLOW}⚠️  {passed}/{total} testes passaram ({percentage:.0f}%){Colors.END}")
        print(f"{Colors.YELLOW}O sistema pode funcionar, mas há problemas a corrigir.{Colors.END}")
    else:
        print(f"{Colors.RED}❌ Apenas {passed}/{total} testes passaram ({percentage:.0f}%){Colors.END}")
        print(f"{Colors.RED}Corrija os problemas antes de usar o sistema.{Colors.END}")

    print(f"{Colors.BLUE}{'─' * 60}{Colors.END}\n")

    # Retorna código de saída apropriado
    sys.exit(0 if percentage >= 70 else 1)


if __name__ == "__main__":
    asyncio.run(main())
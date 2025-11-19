import asyncio
import os
from dotenv import load_dotenv
from repositories.chroma_repository import get_conversations_repository

# Carrega as variáveis (incluindo a URL da nuvem)
load_dotenv()


async def limpar_banco_remoto():
    print("🔌 Conectando ao Banco de Dados na Nuvem...")
    url = os.getenv("CHROMA_SERVER_URL")
    print(f"   Alvo: {url}")

    try:
        # Obtém o repositório conectado na nuvem
        repo = get_conversations_repository()

        print("🔥 Iniciando exclusão total da coleção...")
        # Chama a função que deleta e recria a coleção
        await repo.delete_collection_data()

        print("✅ SUCESSO! O banco de dados da nuvem foi zerado.")
        print("   Reinicie o backend principal para ressincronizar.")

    except Exception as e:
        print(f"❌ Erro ao limpar: {e}")


if __name__ == "__main__":
    asyncio.run(limpar_banco_remoto())
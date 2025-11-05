# Em backend/routers/evolution.py
# (SUBSTITUA O ARQUIVO INTEIRO POR ESTE)

import httpx
import os
import traceback
from fastapi import APIRouter, Depends, HTTPException, Request, status

from core.security import get_current_active_user, get_current_user
from schemas import UserInDB


# --- Definição completa da classe Colors ---
class Colors:
    RED = '\033[91m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    END = '\033[0m'


def print_error(msg): print(f"{Colors.RED}❌ {msg}{Colors.END}")


def print_warning(msg): print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")


# ---

router = APIRouter(
    prefix="/evolution",
    tags=["Evolution API Proxy"],
    dependencies=[Depends(get_current_active_user)]
)

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "https://evolution-api-129644477821.us-central1.run.app")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")

if not EVOLUTION_API_KEY:
    raise RuntimeError("EVOLUTION_API_KEY não está configurada nas variáveis de ambiente.")


# --- Endpoints de Proxy ---

@router.post("/instance/create_and_get_qr")
async def proxy_get_qr_code(  # Renomeei a função para refletir a nova lógica
        request: Request,
        current_user: UserInDB = Depends(get_current_user)
):
    """
    Faz proxy para OBTER O QR CODE de uma instância existente.
    O frontend chama "create_and_get_qr", mas o que ele realmente quer
    é o QR Code da instância padrão se ela estiver desconectada.
    """
    try:
        try:
            frontend_body = await request.json()
        except Exception:
            frontend_body = {}

            # Usa "cosmos-test" como padrão, que é a instância que já existe
        instance_name = frontend_body.get("instanceName") or "cosmos-test"

        # --- 💡 MUDANÇA DE LÓGICA PRINCIPAL 💡 ---
        # Endpoint para OBTER QR CODE de instância existente
        api_url = f"{EVOLUTION_API_URL}/instance/connect/{instance_name}"

        headers = {"apikey": EVOLUTION_API_KEY}

        async with httpx.AsyncClient() as client:
            # É UMA CHAMADA GET, NÃO POST, E NÃO ENVIA BODY
            response = await client.get(
                api_url,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as e:
        print_error(f"Proxy (get_qr): Erro de Status da API ({e.response.status_code}): {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Erro na Evolution API: {e.response.text}"
        )
    except httpx.ConnectError as e:
        print_error(f"Proxy (get_qr): Erro de Conexão: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Erro de Conexão: Não foi possível conectar à Evolution API."
        )
    except httpx.TimeoutException as e:
        print_error(f"Proxy (get_qr): Timeout: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Timeout: A Evolution API demorou muito para responder."
        )
    except Exception as e:
        print_error(f"Proxy (get_qr): Erro interno inesperado: {repr(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno no proxy: {repr(e)}"
        )


@router.get("/instance/status")
async def proxy_instance_status(
        request: Request,
        current_user: UserInDB = Depends(get_current_user)
):
    """
    Faz proxy da verificação de status da instância para a Evolution API.
    (Esta função já está funcionando corretamente)
    """
    instance_name = request.query_params.get('instanceName') or "cosmos-test"

    if not instance_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O parâmetro 'instanceName' é obrigatório."
        )

    api_url = f"{EVOLUTION_API_URL}/instance/connectionState/{instance_name}"
    headers = {"apikey": EVOLUTION_API_KEY}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, headers=headers, timeout=10.0)
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as e:
        print_error(f"Proxy (status): Erro de Status da API ({e.response.status_code}): {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Erro na Evolution API: {e.response.text}"
        )
    except Exception as e:
        print_error(f"Proxy (status): Erro interno inesperado: {repr(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno no proxy: {repr(e)}"
        )
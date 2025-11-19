# Em backend/routers/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from core.security import get_current_user
from services.websocket_manager import manager # Importa o gerente criado
from schemas import UserInDB # Importa o modelo de usuário

router = APIRouter(
    tags=["WebSocket"]
)

@router.websocket("/ws/{token}")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str, # Captura o token do path (URL)
    # Usa a segurança para autenticar e obter o objeto User
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Endpoint WebSocket para comunicação em tempo real.
    Autentica o usuário usando o token de acesso.
    """
    # Se o Depends(get_current_user) falhar, ele já lança uma 401 e a conexão não é aceita.
    user_id = current_user.username # Usamos o username como ID único do usuário

    try:
        # Conecta o usuário
        await manager.connect(user_id, websocket)

        # Loop principal: mantem a conexão aberta.
        # Podemos esperar por mensagens do cliente aqui (ex: "estou digitando").
        while True:
            # Espera por qualquer mensagem. Se o cliente fechar, levanta WebSocketDisconnect.
            # O `receive_text` é necessário para manter o loop vivo.
            data = await websocket.receive_text()
            # Opcional: Processar mensagens recebidas do cliente (ex: status de digitação)
            # print(f"Cliente {user_id} enviou: {data}")

    except WebSocketDisconnect:
        # Desconecta o usuário quando a aba é fechada ou o app é atualizado
        manager.disconnect(user_id, websocket)
    except Exception as e:
        # Lidar com outros erros
        print(f"❌ Erro no WebSocket do usuário {user_id}: {e}")
        manager.disconnect(user_id, websocket)

# (Lembre-se de criar o arquivo `websocket_manager.py` no `/services`
# com o conteúdo que discutimos na etapa anterior - ele já foi fornecido.)
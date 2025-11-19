# /websocket_manager.py
from typing import Dict, List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # Dicionário para guardar conexões por usuário (ou ID da instância)
        # Formato: { "user_id_1": [websocket1, websocket2] }
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        """ Aceita e armazena uma nova conexão WebSocket. """
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        print(f"Nova conexão: Usuário {user_id} conectado.")

    def disconnect(self, user_id: str, websocket: WebSocket):
        """ Remove uma conexão WebSocket. """
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            print(f"Desconexão: Usuário {user_id} desconectado.")
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def broadcast(self, user_id: str, message_json: dict):
        """ Envia uma mensagem JSON para todas as conexões de um usuário. """
        if user_id in self.active_connections:
            connections = self.active_connections[user_id]
            for connection in connections:
                try:
                    await connection.send_json(message_json)
                except Exception as e:
                    print(f"Erro ao enviar para {user_id}: {e}")
                    # Remove conexões quebradas (opcional, mas bom)
                    # self.disconnect(user_id, connection)

# Instância global do gerenciador
manager = ConnectionManager()
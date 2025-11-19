# Em backend/schemas.py
# (SUBSTITUA o conteúdo deste arquivo)

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any # 💡 ADICIONADO List, Dict, Any

# --- Modelos de Usuário ---
class User(BaseModel):
    """Modelo base para um usuário."""
    username: str
    full_name: Optional[str] = None
    tenant_id: Optional[str] = None

class UserInDB(User):
    """Modelo de usuário como está armazenado no banco (com hash)."""
    hashed_password: str
    disabled: Optional[bool] = False

# --- Modelos de Autenticação ---
class Token(BaseModel):
    """Modelo para a resposta do token de acesso."""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """Modelo para os dados contidos dentro do token JWT."""
    username: Optional[str] = None

# --- Modelos de API ---
class NewConversationRequest(BaseModel):
    """Modelo para a requisição de iniciar uma nova conversa."""
    recipient_number: str = Field(..., description="Número do destinatário no formato DDI+DDD+Número, ex: 5541999999999")
    initial_message: str

# --- 💡 NOVO MODELO DE RESPOSTA ---
class ConversationListResponse(BaseModel):
    """
    Modelo de resposta para a lista de conversas,
    conforme esperado pelo frontend.
    """
    status: str
    conversations: List[Dict[str, Any]]

# ... (código anterior)

class CopilotAnalyzeRequest(BaseModel):
    contact_id: str = Field(..., description="ID do contato")
    query: str = Field(..., description="Mensagem")
    is_private: Optional[bool] = Field(False, description="Se for True, a IA responde ao vendedor, não gera sugestão para o cliente.")

class FetchProfilePictureRequest(BaseModel):
    number: str = Field(..., description="Número do contato (sem @s.whatsapp.net)")
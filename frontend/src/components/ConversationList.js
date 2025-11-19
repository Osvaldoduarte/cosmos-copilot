import React, { useMemo } from 'react';
import { useChat } from '../context/ChatContext';
import { formatContactName, DEFAULT_AVATAR_URL } from '../utils/formatDisplay';

// --- Ícones (Mantidos) ---
const NewChatIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2"/></svg>);
const LogoutIcon = () => (<svg width="20" height="20" viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" stroke="currentColor" strokeWidth="2" fill="none"/><polyline points="16 17 21 12 16 7" stroke="currentColor" strokeWidth="2" fill="none"/><line x1="21" y1="12" x2="9" y2="12" stroke="currentColor" strokeWidth="2"/></svg>);
const SearchIcon = () => (<svg width="20" height="20" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="2" fill="none"/><path d="m21 21-4.35-4.35" stroke="currentColor" strokeWidth="2"/></svg>);

function ConversationList({ onLogout }) {
  const {
    conversations, // Array de conversas do Contexto
    activeConversationId,
    // ✨ 1. FUNÇÃO IMPORTADA: Esta função agora existe no Contexto
    handleConversationSelect,
    handleNewConversationClick,
  } = useChat();

  const sortedConversations = useMemo(() => {
    // 💡 Assumimos que 'conversations' é um ARRAY vindo da API.
    // Usamos o operador spread [...] para garantir que não modificamos o estado diretamente.
    return [...conversations].sort((a, b) => {
      // Usa lastUpdated ou timestamp para ordenar
      return (b.lastUpdated || b.timestamp) - (a.lastUpdated || a.timestamp);
    });
  }, [conversations]); // Depende do array de conversas

  return (
    <div className="conversation-list-panel">
      <div className="conversation-list-header">
        <h3>Conversas</h3>
        <button className="new-chat-btn" onClick={handleNewConversationClick}>
          <NewChatIcon />
        </button>
      </div>

      <div className="search-bar">
        <SearchIcon />
        <input type="text" placeholder="Buscar conversas..." />
      </div>

      <div className="conversation-list">
        {sortedConversations.length > 0 ? (
          sortedConversations.map((convo) => (
            <div
              key={convo.id}
              className={`conversation-item ${convo.id === activeConversationId ? 'active' : ''}`}
              // ✨ 2. CHAMADA CORRETA: O 'onClick' agora chama a função válida
              onClick={() => handleConversationSelect(convo.id)}
            >
              <img
                src={convo.avatar_url || DEFAULT_AVATAR_URL}
                alt="Avatar"
                className="conversation-avatar"
                onError={(e) => { e.target.src = DEFAULT_AVATAR_URL; }}
              />

              <div className="conversation-details">
                <div className="conversation-name">{formatContactName(convo.contact_name)}</div>
                <div className="conversation-snippet">{convo.last_message || '...'}</div>
              </div>
              {convo.unread && <div className="unread-dot"></div>}
            </div>
          ))
        ) : (
          <div className="empty-list-placeholder">
            Nenhuma conversa iniciada.
          </div>
        )}
      </div>

      <div className="conversation-list-footer">
        <button className="logout-btn" onClick={onLogout}>
          <LogoutIcon />
          Sair
        </button>
      </div>
    </div>
  );
}

export default ConversationList;
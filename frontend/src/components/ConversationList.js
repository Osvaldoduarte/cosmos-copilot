// Em frontend/src/components/ConversationList.js
// (SUBSTITUA o conteúdo deste arquivo)

import React, { useMemo } from 'react';
import { useChat } from '../context/ChatContext';
// 💡 Importa o formatador e a URL padrão
import { formatContactName, DEFAULT_AVATAR_URL } from '../utils/formatDisplay';

// --- ÍCONES (Restaurados) ---
const NewChatIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2"/></svg>);
const LogoutIcon = () => (<svg width="20" height="20" viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" stroke="currentColor" strokeWidth="2" fill="none"/><polyline points="16 17 21 12 16 7" stroke="currentColor" strokeWidth="2" fill="none"/><line x1="21" y1="12" x2="9" y2="12" stroke="currentColor" strokeWidth="2"/></svg>);
const SearchIcon = () => (<svg width="20" height="20" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="2" fill="none"/><path d="m21 21-4.35-4.35" stroke="currentColor" strokeWidth="2"/></svg>);
// --- Fim dos Ícones ---

function ConversationList({ onLogout }) {
  const {
    conversations,
    activeConversationId,
    handleConversationSelect,
    handleNewConversationClick,
  } = useChat();

  const sortedConversations = useMemo(() => {
    return Object.values(conversations).sort((a, b) => {
      // 💡 Fallback para 'timestamp' (do sync) se 'lastUpdated' não existir
      return (b.lastUpdated || b.timestamp) - (a.lastUpdated || a.timestamp);
    });
  }, [conversations]);

  return (
    <div className="conversation-list-panel">
      {/* --- CABEÇALHO --- */}
      <div className="conversation-list-header">
        <h3>Conversas</h3>
        <button className="new-chat-btn" onClick={handleNewConversationClick}>
          <NewChatIcon />
        </button>
      </div>

      {/* --- BARRA DE BUSCA --- */}
      <div className="search-bar">
        <SearchIcon />
        <input type="text" placeholder="Buscar conversas..." />
      </div>

      {/* --- LISTA DE CONVERSAS --- */}
      <div className="conversation-list">
        {sortedConversations.length > 0 ? (
          sortedConversations.map((convo) => (
            <div
              key={convo.id}
              className={`conversation-item ${convo.id === activeConversationId ? 'active' : ''}`}
              onClick={() => handleConversationSelect(convo.id)}
            >
              {/* 💡 CORREÇÃO 1: Adiciona o Avatar (lendo avatar_url do backend) */}
              <img
                src={convo.avatar_url || DEFAULT_AVATAR_URL}
                alt="Avatar"
                className="conversation-avatar" // (CSS adicionado no index.css)
              />

              <div className="conversation-details">
                {/* 💡 CORREÇÃO 2: Usa contact_name */}
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

      {/* --- RODAPÉ --- */}
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
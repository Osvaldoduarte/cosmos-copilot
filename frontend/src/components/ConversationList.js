// Em frontend/src/components/ConversationList.js
import React, { useState, useMemo } from 'react';
import Fuse from 'fuse.js';
import { DEFAULT_AVATAR_URL } from '../utils/formatDisplay';

// Ícone simples de pesquisa
const SearchIcon = () => (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>);

const NewChatIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>);

const LogoutIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>);


function ConversationList({ conversations, activeConversationId, onConversationSelect, onNewConversationClick, onLogout }) {
  const [searchTerm, setSearchTerm] = useState('');

const fuseOptions = {
    keys: [
      { name: 'name', weight: 0.7 },
      { name: 'messages.text', weight: 0.3 }
    ],
    includeScore: false,
    shouldSort: true,
    threshold: 0.4,
    minMatchCharLength: 2,
    // --- NOVAS OPÇÕES PARA MELHORAR BUSCA DE FRASES ---
    ignoreLocation: true, // Permite que a frase seja encontrada em qualquer lugar do texto
    //distance: 100,      // (Opcional) Define o quão longe as palavras podem estar (pode precisar ajustar)
    //useExtendedSearch: false, // Desativar pode ajudar em alguns casos de busca de substring
    // --------------------------------------------------
    findAllMatches: false,
  };

  // Usamos useMemo para otimizar: a instância do Fuse só é recriada se a lista de conversas mudar.
  const fuse = useMemo(() => new Fuse(conversations, fuseOptions), [conversations]);

  // A filtragem agora usa o fuse.search()
  const filteredConversations = useMemo(() => {
    if (!searchTerm.trim() || searchTerm.trim().length < fuseOptions.minMatchCharLength) {
      // Se a busca estiver vazia ou muito curta, retorna a lista original
      return conversations;
    } else {
      // Executa a busca fuzzy e retorna os resultados (o Fuse retorna { item: convo })
      return fuse.search(searchTerm.trim()).map(result => result.item);
    }
  }, [searchTerm, conversations, fuse]); // Recalcula apenas se o termo ou as conversas mudarem

  return (
  <div className="conversation-list-panel">
    {/* Cabeçalho unificado com o título e o botão */}
    <div className="conversation-list-header">
      <h2>Conversas</h2>
      <button className="new-chat-btn" onClick={onNewConversationClick}>
        <NewChatIcon />
      </button>
    </div>

    {/* Barra de pesquisa logo abaixo do cabeçalho */}
    <div className="search-bar">
      <SearchIcon />
      <input
        type="text"
        placeholder="Pesquisar ou começar uma nova conversa"
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
      />
    </div>

    {/* Lista de conversas filtradas */}
<div className="conversation-list">
        {filteredConversations.map(convo => {
          // A lógica de encontrar a mensagem relevante para exibição continua a mesma
          const displayMessage = searchTerm.trim() ?
            (() => {
              const term = searchTerm.toLowerCase();
              const firstMatch = Array.isArray(convo.messages)
                ? convo.messages.find(msg => msg.text && msg.text.toLowerCase().includes(term)) // Ainda usamos 'includes' aqui para highlight simples
                : null;
              return firstMatch ? firstMatch.text : convo.lastMessage;
            })()
          : convo.lastMessage;

          return (
            <div
              key={convo.id}
              className={`conversation-item ${convo.id === activeConversationId ? 'active' : ''}`}
              onClick={() => onConversationSelect(convo.id)}
            >
              <img src={convo.avatarUrl || DEFAULT_AVATAR_URL} alt={convo.name} className="avatar" />
              <div className="conversation-details">
                <div className="conversation-header">
                  <span className="conversation-name">{convo.name}</span>
                </div>
                {/* Exibe a mensagem relevante encontrada ou a última */}
                <p className="last-message">{displayMessage}</p>
              </div>
              {convo.unread && (
                <div className="unread-dot">
                  {convo.unreadCount > 0 ? convo.unreadCount : ''}
                </div>
              )}
            </div>
          );
        })}
      </div>
    <div className="conversation-list-footer">
        <button className="logout-btn" onClick={onLogout}>
          <LogoutIcon />
          <span>Sair</span>
        </button>
      </div>
  </div>
);
}

export default ConversationList;
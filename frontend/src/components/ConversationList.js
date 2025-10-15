// Em frontend/src/components/ConversationList.js

import React, { useState } from 'react';


// Ícone simples de pesquisa
const SearchIcon = () => (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>);

const NewChatIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>);


function ConversationList({ conversations, activeConversationId, onConversationSelect, onNewConversationClick }) {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredConversations = conversations.filter(convo =>
    convo.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

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
      {filteredConversations.map(convo => (
        <div
          key={convo.id}
          className={`conversation-item ${convo.id === activeConversationId ? 'active' : ''}`}
          onClick={() => onConversationSelect(convo.id)}
        >
          <img src={convo.avatarUrl || `https://i.pravatar.cc/150?u=${convo.id}`} alt={convo.name} className="avatar" />
          <div className="conversation-details">
            <div className="conversation-header">
              <span className="conversation-name">{convo.name}</span>
            </div>
            <p className="last-message">{convo.lastMessage}</p>
          </div>
          {convo.unread && <div className="unread-dot"></div>}
        </div>
      ))}
    </div>
  </div>
);
}

export default ConversationList;
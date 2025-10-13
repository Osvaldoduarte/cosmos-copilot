import React from 'react';

function ConversationList({ conversations, activeConversationId, onConversationSelect }) {
  return (
    <div className="conversation-list-panel">
      <div className="conversation-list">
        {conversations.map(convo => (
          <div
            key={convo.id}
            className={`conversation-item ${convo.id === activeConversationId ? 'active' : ''}`}
            onClick={() => onConversationSelect(convo.id)}
          >
            <img src={convo.avatarUrl} alt={convo.name} className="avatar" />
            <div className="conversation-details">
              <div className="conversation-header">
                <span className="conversation-name">{convo.name}</span>
                <span className="conversation-timestamp">{convo.timestamp}</span>
              </div>
              <p className="last-message">{convo.lastMessage}</p>
            </div>
            {/* MUDANÇA AQUI: Adiciona a bolinha de notificação se a conversa não foi lida */}
            {convo.unread && <div className="unread-dot"></div>}
          </div>
        ))}
      </div>
    </div>
  );
}

export default ConversationList;
import React, { useState, useEffect, useRef } from 'react';
import ReactPlayer from 'react-player';
import { formatContactName, formatMessageTimestamp } from '../utils/formatDisplay';

// Ícones
const SendIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path></svg>);
const AttachIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5a2.5 2.5 0 0 1 5 0v10.5c0 .83-.67 1.5-1.5 1.5s-1.5-.67-1.5-1.5V6H10v9.5a2.5 2.5 0 0 0 5 0V5c-2.21 0-4 1.79-4 4v11.5a5.002 5.002 0 0 0 10 0V6h-1.5z"></path></svg>);
const MoreVertIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"></path></svg>);
const AiIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M19.43..."></path></svg>);

const isYouTubeLink = (text) => {
  if (typeof text !== 'string') return false;
  const youtubeRegex = /^(https?:\/\/(?:www\.)?(?:m\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=|embed\/|v\/|)([\w-]{11})(?:\S+)?)$/;
  return youtubeRegex.test(text);
};

// NOVO: Componente para a tela de boas-vindas
const WelcomePanel = () => (
  <div className="chat-panel welcome-panel">
    <div className="welcome-content">
      {/* Você pode adicionar um ícone ou logo aqui se desejar */}
      <h2>Seja Bem-vindo!</h2>
      <p>Selecione uma conversa na lista à esquerda para começar a usar o Cosmos Copilot.</p>
    </div>
  </div>
);

function ChatPanel({ activeConversation, onSellerResponseSubmit, isLoading }) {
  const [sellerResponse, setSellerResponse] = useState('');
  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeConversation?.messages]);

  const handleSellerSubmit = (e) => {
    e.preventDefault();
    if (!sellerResponse.trim()) return;
    onSellerResponseSubmit(sellerResponse);
    setSellerResponse('');
  };

  // MUDANÇA PRINCIPAL: Verifica se há uma conversa ativa
  if (!activeConversation) {
    return <WelcomePanel />;
  }

  // O resto do componente só é renderizado se houver uma conversa ativa
return (
    <div className="chat-panel">
      <div className="chat-header-active">
        <img src={activeConversation.avatarUrl || `https://i.pravatar.cc/150?u=${activeConversation.id}`} alt={activeConversation.name} className="header-avatar" />
        <span className="header-name">{formatContactName(activeConversation.name)}</span>
        <div className="header-actions"><button><MoreVertIcon /></button></div>
      </div>

      <div className="chat-history-active">
        {activeConversation.messages.map((msg, index) => {
          const isYoutube = isYouTubeLink(msg.text);
          const isDraggable = msg.sender === 'cliente';
          const handleDragStart = (e, text) => {
            e.dataTransfer.setData("text/plain", text);
          };

          return (
            <div key={index} className={`message-bubble-wrapper ${msg.sender}`}>
              <div
                className={`message-bubble ${msg.sender} ${isYoutube ? 'video-bubble' : ''} ${isDraggable ? 'draggable-message' : ''}`}
                draggable={isDraggable}
                onDragStart={isDraggable ? (e) => handleDragStart(e, msg.text) : null}
              >
                {isYoutube ? (
                  <div className="youtube-player-in-chat">
                    <ReactPlayer url={msg.text} controls={true} width='100%' height='100%' />
                  </div>
                ) : (
                  <p>{msg.text}</p>
                )}
                <div className="message-metadata">
                  <span className="message-timestamp">{formatMessageTimestamp(msg.timestamp)}</span>
                </div>
              </div>
            </div>
          );
        })}
        <div ref={chatEndRef} />
      </div>

      <div className="chat-input-area seller-input">
        <form onSubmit={handleSellerSubmit} className="chat-form">
          <button type="button" className="icon-button"><AttachIcon /></button>
          <input type="text" value={sellerResponse} onChange={(e) => setSellerResponse(e.target.value)} placeholder="Mensagem" />
          <button type="submit" className="icon-button"><SendIcon /></button>
        </form>
      </div>
    </div>
  );
}

export default ChatPanel;

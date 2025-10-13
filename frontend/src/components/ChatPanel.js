import React, { useState, useEffect, useRef } from 'react';
import ReactPlayer from 'react-player';

// Ícones
const SendIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path></svg>);
const AttachIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5a2.5 2.5 0 0 1 5 0v10.5c0 .83-.67 1.5-1.5 1.5s-1.5-.67-1.5-1.5V6H10v9.5a2.5 2.5 0 0 0 5 0V5c-2.21 0-4 1.79-4 4v11.5a5.002 5.002 0 0 0 10 0V6h-1.5z"></path></svg>);
const MoreVertIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"></path></svg>);
const AiIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M19.43 12.98c.04-.32.07-.64.07-.98s-.03-.66-.07-.98l2.11-1.65c.19-.15.24-.42.12-.64l-2-3.46c-.12-.22-.39-.3-.61-.22l-2.49 1c-.52-.4-1.08-.73-1.69-.98l-.38-2.65C14.46 2.18 14.25 2 14 2h-4c-.25 0-.46.18-.49-.42l-.38 2.65c-.61-.25-1.17-.59-1.69-.98l-2.49-1c-.23-.08-.49 0-.61.22l-2 3.46c-.13.22-.07.49.12.64l2.11 1.65c-.04.32-.07.65-.07.98s.03.66.07.98l-2.11 1.65c-.19-.15-.24-.42-.12-.64l2 3.46c.12.22.39.3.61-.22l2.49-1c.52.4 1.08.73-1.69.98l.38 2.65c.03.24.24.42.49.42h4c.25 0 .46-.18.49.42l.38-2.65c.61-.25 1.17-.59-1.69.98l2.49 1c.23.08.49 0 .61.22l2-3.46c.12-.22-.07-.49-.12-.64l-2.11-1.65zM12 15.5c-1.93 0-3.5-1.57-3.5-3.5s1.57-3.5 3.5-3.5 3.5 1.57 3.5 3.5-1.57 3.5-3.5 3.5z"></path></svg>);

const isYouTubeLink = (text) => {
  if (typeof text !== 'string') return false;
  const youtubeRegex = /^(https?:\/\/(?:www\.)?(?:m\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=|embed\/|v\/|)([\w-]{11})(?:\S+)?)$/;
  return youtubeRegex.test(text);
};

function ChatPanel({ activeConversation, onCustomerQuerySubmit, onSellerResponseSubmit, isLoading }) {
  const [customerQuery, setCustomerQuery] = useState('');
  const [sellerResponse, setSellerResponse] = useState('');

  // A CORREÇÃO ESTÁ AQUI: A linha abaixo estava faltando
  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeConversation.messages]);

  const handleSellerSubmit = (e) => {
    e.preventDefault();
    if (!sellerResponse.trim()) return;
    onSellerResponseSubmit(sellerResponse);
    setSellerResponse('');
  };

  const handleCustomerSubmit = (e) => {
    // 1. Previne o recarregamento da página, que é o comportamento padrão de um formulário
    e.preventDefault();

    // 2. Garante que não enviamos uma requisição se o campo estiver vazio
    if (!customerQuery.trim()) return;

    // 3. Chama a função do App.js passando APENAS a string da pergunta
    onCustomerQuerySubmit(customerQuery);

    // 4. Limpa o campo de input após o envio
    setCustomerQuery('');
  };

  if (!activeConversation) return <div className="chat-panel"></div>;

  return (
    <div className="chat-panel">
      <div className="chat-header-active">
        <img src={activeConversation.avatarUrl} alt={activeConversation.name} className="header-avatar" />
        <span className="header-name">{activeConversation.name}</span>
        <div className="header-actions"><button><MoreVertIcon /></button></div>
      </div>
       <div className="chat-input-area customer-query-area">
         <form onSubmit={handleCustomerSubmit} className="chat-form">
            <input type="text" value={customerQuery} onChange={(e) => setCustomerQuery(e.target.value)} placeholder="Simular mensagem do cliente..." disabled={isLoading} />
            <button type='submit' disabled={isLoading} className="ai-button"><SendIcon /></button>
          </form>
      </div>

      <div className="chat-history-active">
            {activeConversation.messages.map((msg, index) => {
              const isYoutube = isYouTubeLink(msg.text);

              // MUDANÇA: A lógica de arrastar só se aplica às mensagens do cliente
              const isDraggable = msg.sender === 'cliente';

              const handleDragStart = (e, text) => {
                // "Anexa" o texto da mensagem ao evento de arrastar
                e.dataTransfer.setData("text/plain", text);
              };

              return (
                <div key={index} className={`message-bubble-wrapper ${msg.sender}`}>
                  <div
                    className={`message-bubble ${msg.sender} ${isYoutube ? 'video-bubble' : ''} ${isDraggable ? 'draggable-message' : ''}`}
                    // MUDANÇA: Adiciona as propriedades de arrastar
                    draggable={isDraggable}
                    onDragStart={isDraggable ? (e) => handleDragStart(e, msg.text) : null}
                  >
                    {msg.type === 'audio' && msg.src ? (
                      <audio controls src={msg.src} style={{ width: '250px' }} />
                    ) : isYoutube ? (
                      <div className="youtube-player-in-chat">
                        <ReactPlayer url={msg.text} controls={true} width='100%' height='100%' />
                      </div>
                    ) : (
                      <p>{msg.text}</p>
                    )}
                  </div>
                </div>
              )
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
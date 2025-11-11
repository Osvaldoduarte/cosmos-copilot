// Em frontend/src/components/ChatPanel.js
// (SUBSTITUA o conteúdo deste arquivo)

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { formatContactName, formatMessageTimestamp, DEFAULT_AVATAR_URL } from '../utils/formatDisplay';
import MessageContextMenu from './MessageContextMenu';
import { useChat } from '../context/ChatContext';

// --- Ícones ---
const SendIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path></svg>);
const AttachIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5a2.5 2.5 0 0 1 5 0v10.5c0 .83-.67 1.5-1.5 1.5s-1.5-.67-1.5-1.5V6H13v9.5c0 1.38 1.12 2.5 2.5 2.5s2.5-1.12 2.5-2.5V5a4.5 4.5 0 0 0-9 0v11.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z"></path></svg>);
const BackIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"></path></svg>);
const CopilotIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M12 2L9 9l-7 3 7 3 3 7 3-7 7-3-7-3z"></path></svg>);
const ScrollDownIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M12 16.59l-6-6 1.41-1.41L12 13.77l4.59-4.59L18 10.59z"></path></svg>);
// --- Fim dos Ícones ---

// 💡 Aceita 'onToggleCopilot' e 'onBack' como props
function ChatPanel({ onToggleCopilot, onBack }) {
  const [sellerResponse, setSellerResponse] = useState('');
  const [contextMenu, setContextMenu] = useState({ visible: false, x: 0, y: 0, message: null });
  const [showScrollButton, setShowScrollButton] = useState(false);
  const chatEndRef = useRef(null);
  const chatContainerRef = useRef(null);

  const {
    activeConversationId,
    conversations,
    activeMessages,
    isLoadingMessages,
    handleSuggestionRequest,
    isMobile,
  } = useChat();

  const activeConversation = conversations[activeConversationId] || null;
  const messages = activeMessages;

  // --- Handlers ---
  const scrollToBottom = (behavior = 'auto') => {
    chatEndRef.current?.scrollIntoView({ behavior });
  };
  const handleSellerSubmit = (e) => {
    e.preventDefault();
    console.log("Enviando:", sellerResponse);
    setSellerResponse('');
  };
  const handleMessageContextMenu = (e, msg) => {
    e.preventDefault();
    setContextMenu({ visible: true, x: e.pageX, y: e.pageY, message: msg });
  };
  const handleAnalyzeFromMenu = () => {
    if (contextMenu.message) {
      handleSuggestionRequest(contextMenu.message.content);
    }
    setContextMenu({ visible: false, x: 0, y: 0, message: null });
  };

  // --- Efeitos (Scroll) ---
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleScroll = useCallback(() => {
    const container = chatContainerRef.current;
    if (container) {
        const isScrolledToBottom = container.scrollHeight - container.clientHeight <= container.scrollTop + 100;
        setShowScrollButton(!isScrolledToBottom);
    }
  }, []);

  useEffect(() => {
    const container = chatContainerRef.current;
    if (container) {
        container.addEventListener('scroll', handleScroll);
        return () => container.removeEventListener('scroll', handleScroll);
    }
  }, [handleScroll]);

  if (!activeConversation) {
    return <div className="chat-panel-placeholder">Selecione uma conversa para começar.</div>;
  }

  const contactName = formatContactName(activeConversation.contact_name);
  const avatarUrl = activeConversation.avatar_url || DEFAULT_AVATAR_URL;

  return (
    <div className="chat-panel">
      {/* --- CABEÇALHO --- */}
      <div className="chat-header">
        {/* 💡 Usa as props passadas pelo App.js */}
        {isMobile && (
          <button className="icon-button back-button" onClick={onBack}>
            <BackIcon />
          </button>
        )}
        <img src={avatarUrl} alt="Avatar" className="chat-avatar" />
        <div className="chat-header-info">
          <div className="chat-header-name">{contactName}</div>
        </div>
        {/* 💡 Usa as props passadas pelo App.js */}
        <button className="icon-button" onClick={onToggleCopilot}>
          <CopilotIcon />
        </button>
      </div>

      <div
  className="chat-messages"
  ref={chatContainerRef} // 💡 Ref simplificada
>
  {isLoadingMessages ? (
    <div className="chat-placeholder">Carregando mensagens...</div>
  ) : messages.length === 0 ? (
    <div className="chat-placeholder">Nenhuma mensagem nesta conversa.</div>
  ) : (
    messages.map((msg, index) => {
      const senderType = msg.sender === 'cliente' ? 'client' : 'seller';
      const messageId = String(msg.id || `msg-temp-${index}`);

      // 💡 Lógica unificada.
      // O Draggable foi removido, agora é apenas um 'div' simples,
      // assim como o do 'seller'.
      return (
        <div
          key={messageId}
          className={`message-bubble-row message-${senderType}`}
          // O clique direito (ContextMenu) é mantido
          {...(senderType === 'client' && {
            onContextMenu: (e) => handleMessageContextMenu(e, msg),
          })}
        >
          <div className={`message-bubble message-bubble-${senderType}`}>
            <p>{msg.content}</p>
            <div className="message-metadata">
              <span className="message-timestamp">{formatMessageTimestamp(msg.timestamp)}</span>
            </div>
          </div>
        </div>
      );
    })
  )}
  {/* 💡 'provided.placeholder' removido */}
  <div ref={chatEndRef} />
</div>

      {showScrollButton && (
        <button className="scroll-to-bottom-btn" onClick={() => scrollToBottom('smooth')}>
          <ScrollDownIcon />
        </button>
      )}

      {/* --- INPUT DE MENSAGEM --- */}
      <div className="chat-input-area seller-input">
        <form onSubmit={handleSellerSubmit} className="chat-form">
          <button type="button" className="icon-button"><AttachIcon /></button>
          <input type="text" value={sellerResponse} onChange={(e) => setSellerResponse(e.target.value)} placeholder="Mensagem" />
          <button type="submit" className="icon-button"><SendIcon /></button>
        </form>
      </div>

      {contextMenu.visible && (
        <MessageContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          onAnalyze={handleAnalyzeFromMenu}
          onClose={() => setContextMenu({ visible: false, x: 0, y: 0, message: null })}
        />
      )}
    </div>
  );
}

export default ChatPanel;
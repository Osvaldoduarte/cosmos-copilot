import React, { useState, useEffect, useRef, useCallback } from 'react';
import ReactPlayer from 'react-player';
import { formatContactName, formatMessageTimestamp, DEFAULT_AVATAR_URL } from '../utils/formatDisplay';
import MessageContextMenu from './MessageContextMenu'; // Importa nosso novo componente
// Ícones

const SendIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path></svg>);
const AttachIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5a2.5 2.5 0 0 1 5 0v10.5c0 .83-.67 1.5-1.5 1.5s-1.5-.67-1.5-1.5V6H10v9.5a2.5 2.5 0 0 0 5 0V5c-2.21 0-4 1.79-4 4v11.5a5.002 5.002 0 0 0 10 0V6h-1.5z"></path></svg>);
const MoreVertIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"></path></svg>);
const ScrollDownIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"></path></svg>);
const BackIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"></path></svg>);
const CopilotIcon = () => <>✨</>; // Ícone de Varinha Mágica


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



function ChatPanel({ activeConversationId, activeConversation, onSellerResponseSubmit, isLoading, onToggleCopilot, isMobile, unreadCount, onBack, onMessageDragAnalyze }) {
  const [sellerResponse, setSellerResponse] = useState('');
  const chatEndRef = useRef(null);
  const chatContainerRef = useRef(null);

  // ===================================================================
  // PASSO 1 DA LÓGICA: ESTADO PARA CONTROLAR A VISIBILIDADE DO BOTÃO
  // ===================================================================
  const [showScrollButton, setShowScrollButton] = useState(false);

  // ===================================================================
  // PASSO 2 DA LÓGICA: FUNÇÃO PARA ROLAR PARA O FINAL
  // ===================================================================
  const scrollToBottom = useCallback((behavior = 'smooth') => {
    chatEndRef.current?.scrollIntoView({ behavior });
  }, []);

  // ===================================================================
  // PASSO 3 DA LÓGICA: DETECTOR DE SCROLL
  // ===================================================================
const handleScroll = useCallback(() => {
    // ================== ADICIONE ESTA LINHA ==================
    // Se um scroll acontecer, cancela qualquer tentativa de abrir o menu de contexto.
    clearTimeout(longPressTimer.current);
    // =======================================================

    const container = chatContainerRef.current;
    if (!container) return;

    const isScrolledUp = container.scrollHeight - container.scrollTop > container.clientHeight + 10;
    setShowScrollButton(isScrolledUp);
  }, []);

  // ===================================================================
  // PASSO 4 DA LÓGICA: EFEITOS DE SCROLL AUTOMÁTICO
  // ===================================================================
  // Efeito 1: Rola para o final (instantaneamente) sempre que a conversa é trocada.
  useEffect(() => {
    scrollToBottom('auto');
  }, [activeConversationId, scrollToBottom]);

  // Efeito 2: Rola para o final (suavemente) quando novas mensagens chegam,
  // mas SÓ se o usuário já estiver no final da conversa.
  useEffect(() => {
    const container = chatContainerRef.current;
    if (!container) return;
    const isScrolledNearBottom = container.scrollHeight - container.scrollTop <= container.clientHeight + 1;
    if (isScrolledNearBottom) {
      scrollToBottom('smooth');
    }
  }, [activeConversation?.messages, scrollToBottom]);


  // O resto das suas funções (handleSellerSubmit, etc.) continua igual...
  const handleSellerSubmit = (e) => {
    e.preventDefault();
    if (!sellerResponse.trim()) return;
    onSellerResponseSubmit(sellerResponse);
    setSellerResponse('');
  };

  const [contextMenu, setContextMenu] = useState({ visible: false, x: 0, y: 0, text: '' });
  const longPressTimer = useRef();

  const handleTouchStart = (e, text) => {
    // Inicia um timer. Se o usuário segurar por 500ms, o menu abre.
    longPressTimer.current = setTimeout(() => {
      const touch = e.touches[0];
      setContextMenu({
        visible: true,
        x: touch.clientX,
        y: touch.clientY,
        text: text
      });
    }, 500); // 500ms = meio segundo
  };

  const handleTouchEnd = () => {
    // Se o usuário soltar o dedo ANTES do timer terminar, cancela a abertura do menu.
    clearTimeout(longPressTimer.current);
  };

  const handleAnalyzeFromMenu = () => {
    if (contextMenu.text) {
      onMessageDragAnalyze(contextMenu.text);
    }
    // Fecha o menu após a ação
    setContextMenu({ visible: false, x: 0, y: 0, text: '' });
  };

  if (!activeConversation) {
    return <WelcomePanel />;
  }

return (
    <div className="chat-panel">
      {/* ===================================================================
          A LÓGICA DO NOVO CABEÇALHO ESTÁ AQUI
          =================================================================== */}
      <div className={`chat-header-active ${isMobile ? 'mobile' : ''}`}>
        {isMobile ? (
          // --- LAYOUT DO CABEÇALHO PARA MOBILE ---
          <>
            <div className="header-left">
              <button className="back-button icon-button" onClick={onBack}>
                <BackIcon />
                {unreadCount > 0 && <span className="unread-badge">{unreadCount}</span>}
              </button>
            </div>
            <div className="header-center">
              <img src={activeConversation.avatarUrl || DEFAULT_AVATAR_URL} alt={activeConversation.name} className="header-avatar" />
              <div className="header-center-text">
                <span className="header-name">{formatContactName(activeConversation.name)}</span>
                {/* Futuramente, o status "digitando..." virá aqui */}
              </div>
            </div>
            <div className="header-right">
              <button className="icon-button" onClick={onToggleCopilot}>
                <CopilotIcon />
              </button>
            </div>
          </>
        ) : (
          // --- LAYOUT DO CABEÇALHO PARA DESKTOP (SIMPLES) ---
          <>
            <img src={activeConversation.avatarUrl || DEFAULT_AVATAR_URL} alt={activeConversation.name} className="header-avatar" />
            <span className="header-name">{formatContactName(activeConversation.name)}</span>
            {/* O botão de 3 pontos foi removido, como você pediu */}
          </>
        )}
      </div>

<div className="chat-history-active" ref={chatContainerRef} onScroll={handleScroll}>
        {activeConversation.messages.map((msg, index) => {
          const isYoutube = isYouTubeLink(msg.text);
          const isDraggable = msg.sender === 'cliente';

return (
            <div key={index} className={`message-bubble-wrapper ${msg.sender}`}>
<div
                className={`message-bubble ${msg.sender} ${isDraggable ? 'draggable-message' : ''}`}
                // Apenas os eventos de início e fim do toque são necessários aqui
                onTouchStart={isDraggable ? (e) => handleTouchStart(e, msg.text) : null}
                onTouchEnd={isDraggable ? handleTouchEnd : null}
                onContextMenu={(e) => e.preventDefault()}
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
{/* ===================================================================
          PASSO 5 DA LÓGICA: RENDERIZAÇÃO CONDICIONAL DO BOTÃO
          =================================================================== */}
      {showScrollButton && (
        <button className="scroll-to-bottom-btn" onClick={() => scrollToBottom('smooth')}>
          <ScrollDownIcon />
        </button>
      )}
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
          onClose={() => setContextMenu({ visible: false, x: 0, y: 0, text: '' })}
        />
      )}
    </div>
  );
}

export default ChatPanel;

// /frontend/src/components/ChatPanel.js
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import api from '../services/api';
import axios from 'axios';
import { formatContactName, formatMessageTimestamp, DEFAULT_AVATAR_URL } from '../utils/formatDisplay';
import MessageContextMenu from './MessageContextMenu';
import { useChat } from '../context/ChatContext';
import CustomAudioPlayer from './CustomAudioPlayer';
import '../styles/chat.css';

// --- CONSTANTES ---
const EVOLUTION_URL = process.env.REACT_APP_EVOLUTION_URL;
const EVOLUTION_API_KEY = process.env.REACT_APP_EVOLUTION_API_KEY;

// --- ÍCONES (Mantidos) ---
const SendIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path></svg>);
const AttachIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5a2.5 2.5 0 0 1 5 0v10.5c0 .83-.67 1.5-1.5 1.5s-1.5-.67-1.5-1.5V6H13v9.5c0 1.38 1.12 2.5 2.5 2.5s2.5-1.12 2.5-2.5V5a4.5 4.5 0 0 0-9 0v11.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z"></path></svg>);
const BackIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"></path></svg>);
const BrainTabIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3l1.912 5.813a2 2 0 0 0 1.272 1.272L21 12l-5.813 1.912a2 2 0 0 0 -1.272 1.272L12 21l-1.912-5.813a2 2 0 0 0 -1.272-1.272L3 12l5.813-1.912a2 2 0 0 0 1.272-1.272L12 3z" /><path d="M5 3v4" /><path d="M9 3v4" /><path d="M3 5h4" /><path d="M3 9h4" /></svg>);
const ScrollDownIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M12 16.59l-6-6 1.41-1.41L12 13.77l4.59-4.59L18 10.59z"></path></svg>);
const WelcomeIcon = () => (<svg width="80" height="80" viewBox="0 0 24 24" fill="none" style={{ opacity: 0.5, marginBottom: '20px' }}><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>);
const CloseIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" /></svg>);
const MagicIcon = () => <span style={{ fontSize: '1.2em' }}>✨</span>;

// --- CACHE GLOBAL DE MÍDIA (Evita re-download ao navegar) ---
const MEDIA_CACHE = new Map();

// --- COMPONENTE DE MÍDIA ASSÍNCRONA ---
const AsyncMedia = ({ media, rawMessage, onImageClick }) => {
  const [src, setSrc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const loadMedia = async () => {
      // Gera chave de cache única
      const cacheKey = media.url || (rawMessage ? (rawMessage.key?.id || JSON.stringify(rawMessage).slice(0, 100)) : null);

      // 1. Verifica Cache Global
      if (cacheKey && MEDIA_CACHE.has(cacheKey)) {
        setSrc(MEDIA_CACHE.get(cacheKey));
        setLoading(false);
        return;
      }

      // 2. Se já tem URL pública válida (e NÃO é do WhatsApp), usa direto
      const isWhatsappUrl = media.url && media.url.includes('whatsapp.net');

      if (media.url && (media.url.startsWith('http') || media.url.startsWith('data:')) && !isWhatsappUrl) {
        setSrc(media.url);
        setLoading(false);
        if (cacheKey) MEDIA_CACHE.set(cacheKey, media.url);
        return;
      }

      // 3. Se tem rawMessage, tenta baixar do backend
      if (rawMessage) {
        try {
          const res = await api.post('/evolution/media/download', { message: rawMessage });

          if (isMounted && res.data && res.data.base64) {
            const mimeType = media.type === 'image' ? 'image/jpeg' :
              media.type === 'audio' ? 'audio/ogg' :
                media.type === 'video' ? 'video/mp4' :
                  media.type === 'sticker' ? 'image/webp' : 'application/octet-stream';
            const base64Src = `data:${mimeType};base64,${res.data.base64}`;

            // Salva no cache
            if (cacheKey) MEDIA_CACHE.set(cacheKey, base64Src);

            setSrc(base64Src);
          } else {
            if (isMounted) setError(true);
          }
        } catch (err) {
          console.error("AsyncMedia: Erro ao baixar mídia:", err);
          if (isMounted) setError(true);
        } finally {
          if (isMounted) setLoading(false);
        }
      } else {
        if (isMounted) {
          setLoading(false);
          setError(true);
        }
      }
    };

    loadMedia();

    return () => { isMounted = false; };
  }, [media, rawMessage]);

  if (loading) return <div className="media-loading"><div className="spinner-dot"></div></div>;
  if (error || !src) return <div className="media-error">Mídia indisponível</div>;

  if (media.type === 'audio') {
    return (
      <div className="media-content">
        <CustomAudioPlayer src={src} avatar={media.avatar} />
      </div>
    );
  }

  if (media.type === 'image' || media.type === 'sticker') {
    return (
      <div className="media-content">
        <img
          src={src}
          alt="Mídia"
          className={media.type === 'sticker' ? "chat-media-sticker" : "chat-media-img clickable"}
          onClick={() => media.type !== 'sticker' && onImageClick && onImageClick(src)}
          style={media.type === 'sticker' ? { maxWidth: '150px', objectFit: 'contain' } : {}}
        />
      </div>
    );
  }

  if (media.type === 'video') {
    return (
      <div className="media-content">
        <video controls className="chat-media-video">
          <source src={src} type="video/mp4" />
          Seu navegador não suporta vídeos.
        </video>
      </div>
    );
  }

  return null;
};

function ChatPanel({ onToggleCopilot, onBack }) {
  // --- STATE HOOKS ---
  const [sellerResponse, setSellerResponse] = useState('');
  const [contextMenu, setContextMenu] = useState({ visible: false, x: 0, y: 0, message: null });
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [profileData, setProfileData] = useState(null);
  const [isLoadingProfile, setIsLoadingProfile] = useState(false);
  const [lightboxImage, setLightboxImage] = useState(null);

  // 👤 Estados para edição de nome
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState('');

  // --- REF HOOKS ---
  const chatEndRef = useRef(null);
  const chatContainerRef = useRef(null);

  // --- CONTEXT HOOK ---
  const {
    activeConversationId,
    conversations,
    messages,
    isLoadingMessages, // Estado de loading do histórico
    handleSuggestionRequest,
    handleSendMessage,
    handleSendReaction, // 👍 NOVO
    handleUpdateCustomName, // 👤 NOVO
    handleRefreshProfile,   // 🔄 NOVO
    isMobile, // Estado para o botão de voltar
    isCopilotOpen,
    handleToggleCopilot,
    // Sales Context
    salesContext,
    analyzeSalesContext,
    // 🎯 Drag-and-Drop state compartilhado
    isDragging, setIsDragging, draggedMessage, setDraggedMessage
  } = useChat();

  // --- MEMO HOOK (Calcula o objeto da conversa ativa) ---
  const activeConversation = useMemo(() => {
    if (!activeConversationId) return null;
    return conversations.find(c => c.id === activeConversationId) || null;
  }, [conversations, activeConversationId]);

  // ✨ CORREÇÃO CRÍTICA: Garante que 'messages' NUNCA seja undefined
  // const messages = activeMessages || []; // REMOVIDO pois agora vem do context

  // --- CALLBACK HOOKS ---
  const scrollToBottom = (behavior = 'auto') => { chatEndRef.current?.scrollIntoView({ behavior }); };

  const handleSellerSubmit = async (e) => {
    e.preventDefault();
    if (!sellerResponse.trim() || !activeConversation) return;
    const msg = sellerResponse;
    setSellerResponse('');
    await handleSendMessage(msg, activeConversation.id);
    scrollToBottom('smooth');
  };

  const handleMessageContextMenu = (e, msg) => { e.preventDefault(); setContextMenu({ visible: true, x: e.pageX, y: e.pageY, message: msg }); };

  const handleAnalyzeFromMenu = () => {
    if (contextMenu.message && activeConversation) handleSuggestionRequest(contextMenu.message.content, activeConversation.id);
    setContextMenu({ visible: false, x: 0, y: 0, message: null });
  };

  // 🎯 Drag-and-Drop Handlers
  const handleDragStart = (e, msg) => {
    if (msg.sender !== 'cliente') {
      e.preventDefault();
      return;
    }

    // Define dados para transfer
    e.dataTransfer.effectAllowed = 'copy';
    e.dataTransfer.setData('text/plain', msg.content);
    e.dataTransfer.setData('application/json', JSON.stringify({
      content: msg.content,
      sender: msg.sender,
      timestamp: msg.timestamp
    }));

    // Atualiza estado compartilhado
    setIsDragging(true);
    setDraggedMessage(msg);

    // Visual feedback
    e.currentTarget.style.opacity = '0.5';
  };

  const handleDragEnd = (e) => {
    setIsDragging(false);
    setDraggedMessage(null);
    e.currentTarget.style.opacity = '1';
  };

  const handleScroll = useCallback(() => {
    const c = chatContainerRef.current;
    if (c) setShowScrollButton(c.scrollHeight - c.clientHeight > c.scrollTop + 100);
  }, []);

  // --- EFEITOS ---

  // Efeito 1: Limpeza de perfil ao trocar de conversa
  useEffect(() => {
    if (activeConversation) { setProfileData(null); }
  }, [activeConversation ? activeConversation.id : null]);

  // Efeito 2: Busca de Perfil
  useEffect(() => {
    if (isProfileOpen && activeConversation) {
      const fetchProfileInfo = async () => {
        setIsLoadingProfile(true);
        const basicData = {
          name: activeConversation.contact_name || 'Contato',
          profilePictureUrl: activeConversation.avatar_url || DEFAULT_AVATAR_URL,
          number: activeConversation.id.split('@')[0]
        };
        setProfileData(basicData);

        try {
          const number = activeConversation.id.replace('@s.whatsapp.net', '');
          const instanceName = activeConversation.instance || 'cosmos-test';
          let dbInfo = {};

          try {
            const { data } = await api.get(`/contacts/info/${number}`);
            dbInfo = data;
          } catch (e) { }

          let livePicUrl = null;
          try {
            const picRes = await axios.post(`${EVOLUTION_URL}/chat/fetchProfilePictureUrl/${instanceName}`, { number: number }, { headers: { 'apikey': EVOLUTION_API_KEY } });
            livePicUrl = picRes.data?.profilePictureUrl || picRes.data?.picture;
          } catch (e) { }

          setProfileData(prev => ({
            ...prev,
            ...dbInfo,
            name: dbInfo.pushName || dbInfo.name || basicData.name,
            profilePictureUrl: livePicUrl || dbInfo.profilePictureUrl || basicData.profilePictureUrl
          }));

        } catch (err) {
          console.error("Erro ao buscar perfil:", err);
        } finally {
          setIsLoadingProfile(false);
        }
      };
      fetchProfileInfo();
    }
  }, [isProfileOpen, activeConversation]);

  // Efeito 3: Scroll para o fundo
  useEffect(() => { scrollToBottom(); }, [messages]);

  // Efeito 4: Listener de scroll
  useEffect(() => {
    const c = chatContainerRef.current;
    if (c) {
      c.addEventListener('scroll', handleScroll);
      return () => c.removeEventListener('scroll', handleScroll);
    }
  }, [handleScroll]);


  // -----------------------------------------------------------------
  // CLÁUSULA DE GUARDA (Execução Condicional - PONTO SEGURO)
  // -----------------------------------------------------------------

  // Se a conversa for nula, renderize a tela de boas-vindas e SAIA.
  if (!activeConversation) {
    return (
      <div className="chat-welcome-screen">
        <div className="welcome-content">
          <WelcomeIcon />
          <h2>Cosmos Copilot</h2>
          <p>Selecione uma conversa.</p>
          <div className="welcome-badge">
            <span className="status-dot"></span> Sistema Conectado
          </div>
        </div>
      </div>
    );
  }



  // --- RENDERIZADOR DE CONTEÚDO ---
  const renderMessageContent = (msg) => {
    // Suporta tanto o formato antigo quanto o novo
    const raw_message = msg.raw_message || null;
    const content = msg.content;
    const media_url = msg.media_url;
    const media_type = msg.media_type;

    // --- IMAGEM / VÍDEO / STICKER ---
    if (media_type && (media_type === 'image' || media_type === 'video' || media_type === 'sticker')) {
      return (
        <div className="media-wrapper">
          <AsyncMedia
            media={{ type: media_type, url: media_url }}
            rawMessage={raw_message}
            onImageClick={setLightboxImage}
          />
          {content &&
            content !== '📷 [Imagem]' &&
            content !== '🎥 [Vídeo]' &&
            content !== '[IMAGEM]' &&
            content !== '[VÍDEO]' &&
            <p className="media-caption">{content}</p>
          }
        </div>
      );
    }

    // --- ÁUDIO COM TRANSCRIÇÃO ---
    if (media_type === 'audio') {
      const isClient = msg.sender === 'cliente';
      const avatarUrl = isClient ? finalAvatar : 'https://cdn-icons-png.flaticon.com/512/149/149071.png';

      // Extrai transcrição se houver
      let transcription = null;
      if (content && content.includes('🎤 [Áudio]')) {
        const parts = content.split('🎤 [Áudio]');
        if (parts.length > 1 && parts[1].trim()) {
          transcription = parts[1].trim();
        }
      }

      return (
        <div className="media-wrapper">
          <AsyncMedia
            media={{ type: 'audio', url: media_url, avatar: avatarUrl }}
            rawMessage={raw_message}
          />
          {transcription && (
            <AudioTranscription text={transcription} />
          )}
        </div>
      );
    }

    // Fallback: apenas texto
    return <p>{content}</p>;
  };

  // --- COMPONENTE DE TRANSCRIÇÃO ---
  const AudioTranscription = ({ text }) => {
    const [isOpen, setIsOpen] = useState(false);

    return (
      <div className="audio-transcription-container">
        <button
          className="transcription-toggle-btn"
          onClick={(e) => { e.stopPropagation(); setIsOpen(!isOpen); }}
          title="Ver transcrição"
        >
          <span>Ver transcrição</span>
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            style={{ transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}
          >
            <path fill="currentColor" d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z" />
          </svg>
        </button>
        {isOpen && (
          <div className="transcription-text animate-fade-in">
            {text}
          </div>
        )}
      </div>
    );
  };



  // --- VARIÁVEIS DE RENDERIZAÇÃO ---
  const basicName = formatContactName(activeConversation.name);
  const basicAvatar = activeConversation.avatar_url || DEFAULT_AVATAR_URL;
  const displayPhone = activeConversation.id.split('@')[0];
  const finalName = profileData?.pushName || profileData?.name || basicName;
  const finalAvatar = profileData?.profilePictureUrl || profileData?.picture || basicAvatar;
  const isBusiness = profileData?.isBusiness || false;
  const description = profileData?.description || profileData?.status || "Sem recado disponível.";
  const email = profileData?.email || null;
  const website = profileData?.website || null;

  return (
    <div className="chat-panel">
      <div className="chat-header">
        {/* Lógica do Botão de Voltar: Aparece SÓ no Mobile */}
        {isMobile && <button className="icon-button back-button" onClick={onBack}><BackIcon /></button>}
        <div className="clickable-header-area" onClick={() => setIsProfileOpen(true)} title="Ver perfil completo">
          <img src={finalAvatar} alt="Avatar" className="chat-avatar" onError={(e) => e.target.src = DEFAULT_AVATAR_URL} />
          <div className="chat-header-info"><div className="chat-header-name">{finalName}</div></div>
        </div>

        {/* 🧠 SALES CONTEXT BAR (NOVO) */}
        {salesContext && (
          <div className="sales-context-bar animate-fade-in" title={salesContext.advice}>
            <div className="sales-stage-pill">
              <span className="dot"></span>
              {salesContext.stage}
            </div>
            <div className="sales-next-step">
              <span className="step-label">Próximo:</span>
              <span className="step-value">{salesContext.next_step}</span>
            </div>
          </div>
        )}

        <div className="header-actions">
          <button className={`icon-button ${isCopilotOpen ? 'active' : ''}`} onClick={handleToggleCopilot} title="Copilot AI">
            <MagicIcon />
          </button>
        </div>
      </div>

      <div className="chat-messages" ref={chatContainerRef}>
        {/* Mostra o loading se estiver buscando mensagens */}
        {isLoadingMessages ? <div className="chat-placeholder">Carregando mensagens...</div> :
          /* Mostra o placeholder se não houver mensagens */
          messages.length === 0 ? <div className="chat-placeholder">Nenhuma mensagem nesta conversa.</div> :
            /* Renderiza as mensagens */
            messages.map((msg, i) => (
              <div
                key={msg.message_id || msg.id || i}
                className={`message-bubble-row message-${msg.sender === 'cliente' ? 'client' : 'seller'}`}
                draggable={msg.sender === 'cliente'}
                onDragStart={(e) => handleDragStart(e, msg)}
                onDragEnd={handleDragEnd}
                onContextMenu={(e) => msg.sender === 'cliente' && handleMessageContextMenu(e, msg)}
                onTouchStart={(e) => {
                  if (msg.sender !== 'cliente') return;
                  e.persist(); // Persiste o evento para usar no timeout
                  const touch = e.touches[0];
                  // Armazena coordenadas iniciais
                  const startX = touch.clientX;
                  const startY = touch.clientY;

                  // Define timer para long press (500ms)
                  const timer = setTimeout(() => {
                    setContextMenu({ visible: true, x: startX, y: startY, message: msg });
                    // Vibração tátil se disponível
                    if (navigator.vibrate) navigator.vibrate(50);
                  }, 500);

                  // Salva timer e coordenadas no elemento (ou ref, mas aqui direto no handler via closure/dataset é complexo, 
                  // melhor usar refs ou state se fosse componente separado. Como é map, vamos usar uma ref global de controle)
                  window.longPressTimer = timer;
                  window.touchStartX = startX;
                  window.touchStartY = startY;
                }}
                onTouchEnd={() => {
                  if (window.longPressTimer) clearTimeout(window.longPressTimer);
                }}
                onTouchMove={(e) => {
                  const touch = e.touches[0];
                  // Se moveu mais que 10px, cancela o long press (é scroll)
                  if (Math.abs(touch.clientX - window.touchStartX) > 10 || Math.abs(touch.clientY - window.touchStartY) > 10) {
                    if (window.longPressTimer) clearTimeout(window.longPressTimer);
                  }
                }}
              >
                <div className={`message-bubble message-bubble-${msg.sender === 'cliente' ? 'client' : 'seller'} message-with-reactions`}>

                  {renderMessageContent(msg)}

                  <div className="message-metadata">
                    <span className="message-timestamp">{formatMessageTimestamp(msg.timestamp)}</span>
                  </div>

                  {/* 👍 APENAS EXIBE as reações do WhatsApp (sem botão de adicionar) */}
                  {msg.reactions && msg.reactions.length > 0 && (
                    <div className="message-reactions">
                      {msg.reactions.map((r, idx) => (
                        <span key={idx} className={`reaction-badge reaction-from-${r.from}`} title={r.from === 'cliente' ? 'Cliente' : 'Você'}>
                          {r.emoji}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
        <div ref={chatEndRef} />
      </div>

      {showScrollButton && <button className="scroll-to-bottom-btn" onClick={() => scrollToBottom('smooth')}><ScrollDownIcon /></button>}
      {!isCopilotOpen && !isMobile && (<div className="copilot-trigger-tab" onClick={handleToggleCopilot} title="Abrir Copilot"><BrainTabIcon /><span className="tab-label">Copilot</span></div>)}

      <div className="chat-input-area seller-input">
        <form onSubmit={handleSellerSubmit} className="chat-form">
          <button type="button" className="icon-button"><AttachIcon /></button>
          <input type="text" className="chat-input-field" value={sellerResponse} onChange={(e) => setSellerResponse(e.target.value)} placeholder="Mensagem" />
          <button type="submit" className="icon-button"><SendIcon /></button>
        </form>
      </div>

      {contextMenu.visible && <MessageContextMenu x={contextMenu.x} y={contextMenu.y} onAnalyze={handleAnalyzeFromMenu} onClose={() => setContextMenu({ visible: false, x: 0, y: 0, message: null })} />}

      {isProfileOpen && (
        <div className="profile-overlay" onClick={() => setIsProfileOpen(false)}>
          <div className="profile-glass-card" onClick={(e) => e.stopPropagation()}>
            <button className="close-profile-btn" onClick={() => setIsProfileOpen(false)}><CloseIcon /></button>
            {isLoadingProfile && !profileData ? <div className="spinner-dot" style={{ margin: '50px auto' }}></div> : (
              <>
                <img src={finalAvatar} alt="Profile" className="profile-large-avatar" onError={(e) => e.target.src = DEFAULT_AVATAR_URL} />
                <div className="profile-name-container">
                  {isEditingName ? (
                    <div className="profile-name-edit">
                      <input
                        type="text"
                        className="profile-name-input"
                        value={editedName}
                        onChange={(e) => setEditedName(e.target.value)}
                        placeholder="Nome do contato"
                        autoFocus
                      />
                      <div className="profile-edit-actions">
                        <button className="icon-button save-btn" onClick={async () => {
                          if (activeConversation) {
                            await handleUpdateCustomName(activeConversation.id, editedName);
                            setIsEditingName(false);
                            // Atualiza localmente para refletir imediato
                            setProfileData(prev => ({ ...prev, name: editedName, pushName: editedName }));
                          }
                        }}><svg width="20" height="20" viewBox="0 0 24 24"><path fill="currentColor" d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" /></svg></button>
                        <button className="icon-button cancel-btn" onClick={() => setIsEditingName(false)}><CloseIcon /></button>
                      </div>
                    </div>
                  ) : (
                    <div className="profile-name-display">
                      <span className="profile-name-text">{finalName}</span>
                      <button className="icon-button edit-btn" onClick={() => {
                        setEditedName(finalName);
                        setIsEditingName(true);
                      }} title="Editar nome">
                        <svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" /></svg>
                      </button>
                    </div>
                  )}
                  {isBusiness && <span className="business-badge">Business</span>}
                </div>
                <div className="profile-number">+{displayPhone}</div>
                <div className="profile-info-grid">
                  <div className="info-item"><span className="info-label">Recado / Descrição</span><span className="info-value">{description}</span></div>
                  {email && <div className="info-item"><span className="info-label">Email</span><span className="info-value">{email}</span></div>}
                  {website && <div className="info-item"><span className="info-label">Site</span><a href={website} target="_blank" rel="noreferrer" className="info-value" style={{ color: '#4ec9b0' }}>{website}</a></div>}
                  <div className="info-item"><span className="info-label">Histórico</span><span className="info-value">{messages.length} mensagens trocadas</span></div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {lightboxImage && (
        <div className="lightbox-overlay" onClick={() => setLightboxImage(null)}>
          <div className="lightbox-content" onClick={(e) => e.stopPropagation()}>
            <button className="lightbox-close-btn" onClick={() => setLightboxImage(null)}>
              <CloseIcon />
            </button>
            <img src={lightboxImage} alt="Zoom" className="lightbox-img" />
          </div>
        </div>
      )}
    </div>
  );
}

export default ChatPanel;
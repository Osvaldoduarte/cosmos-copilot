// /frontend/src/components/ChatPanel.js
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import api from '../services/api';
import axios from 'axios';
import { formatContactName, formatMessageTimestamp, DEFAULT_AVATAR_URL } from '../utils/formatDisplay';
import MessageContextMenu from './MessageContextMenu';
import { useChat } from '../context/ChatContext';
import CustomAudioPlayer from './CustomAudioPlayer';

// --- CONSTANTES ---
const EVOLUTION_URL = "http://34.29.184.203:8080";
const EVOLUTION_API_KEY = "zrnxcjz8stbsk4qf6c0t6b";
const BACKEND_URL = 'http://127.0.0.1:8000'; // URL local do seu backend

// --- ÍCONES (Mantidos) ---
const SendIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path></svg>);
const AttachIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5a2.5 2.5 0 0 1 5 0v10.5c0 .83-.67 1.5-1.5 1.5s-1.5-.67-1.5-1.5V6H13v9.5c0 1.38 1.12 2.5 2.5 2.5s2.5-1.12 2.5-2.5V5a4.5 4.5 0 0 0-9 0v11.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z"></path></svg>);
const BackIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"></path></svg>);
const BrainTabIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2a3 3 0 0 0-3 3v1a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 11h-2"/><path d="M5 11H3"/><path d="M12 18a3 3 0 0 0 3 3h1a3 3 0 0 0 3-3v-1a3 3 0 0 0-3-3h-1v4Z"/><path d="M12 18a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3v-1a3 3 0 0 1 3-3h1v4Z"/><path d="M12 8v4"/></svg>);
const ScrollDownIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M12 16.59l-6-6 1.41-1.41L12 13.77l4.59-4.59L18 10.59z"></path></svg>);
const WelcomeIcon = () => (<svg width="80" height="80" viewBox="0 0 24 24" fill="none" style={{opacity: 0.5, marginBottom: '20px'}}><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>);
const CloseIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>);


function ChatPanel({ onToggleCopilot, onBack }) {
  // --- STATE HOOKS ---
  const [sellerResponse, setSellerResponse] = useState('');
  const [contextMenu, setContextMenu] = useState({ visible: false, x: 0, y: 0, message: null });
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [profileData, setProfileData] = useState(null);
  const [isLoadingProfile, setIsLoadingProfile] = useState(false);
  const [lightboxImage, setLightboxImage] = useState(null);

  // --- REF HOOKS ---
  const chatEndRef = useRef(null);
  const chatContainerRef = useRef(null);

  // --- CONTEXT HOOK ---
  const {
    activeConversationId,
    conversations,
    activeMessages,
    isLoadingMessages, // Estado de loading do histórico
    handleSuggestionRequest,
    handleSendMessage,
    isMobile, // Estado para o botão de voltar
    isCopilotOpen
  } = useChat();

  // --- MEMO HOOK (Calcula o objeto da conversa ativa) ---
  const activeConversation = useMemo(() => {
    if (!activeConversationId) return null;
    return conversations.find(c => c.id === activeConversationId) || null;
  }, [conversations, activeConversationId]);

  // ✨ CORREÇÃO CRÍTICA: Garante que 'messages' NUNCA seja undefined
  const messages = activeMessages || [];

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
          } catch (e) {}

          let livePicUrl = null;
          try {
             const picRes = await axios.post(`${EVOLUTION_URL}/chat/fetchProfilePictureUrl/${instanceName}`, { number: number }, { headers: { 'apikey': EVOLUTION_API_KEY } });
             livePicUrl = picRes.data?.profilePictureUrl || picRes.data?.picture;
          } catch (e) {}

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

  // --- FUNÇÃO AUXILIAR DO PROXY ---
  const getMediaSource = (url, msgId) => {
    if (!url) return '';
    if (url.startsWith('data:')) return url;

    const encodedUrl = btoa(url);

    return `${BACKEND_URL}/evolution/media-proxy?url=${encodedUrl}&messageId=${msgId || ''}`;
  };

  // --- RENDERIZADOR DE CONTEÚDO ---
  const renderMessageContent = (msg) => {
    const { media_type, media_url, content, message_id } = msg;

    const safeSrc = getMediaSource(media_url, message_id);

    if (media_type === 'audio' && safeSrc) {
      return (
        <div className="media-content">
          <CustomAudioPlayer src={safeSrc} />
          {content && content !== '[ÁUDIO]' && content !== '[Mensagem de Voz]' && <p className="media-caption">{content}</p>}
        </div>
      );
    }

    if (media_type === 'image' && safeSrc) {
      return (
        <div className="media-content">
          <img
            src={safeSrc}
            alt="Imagem"
            className="chat-media-img clickable"
            onClick={() => setLightboxImage(safeSrc)}
          />
          {content && content !== '[IMAGEM]' && <p className="media-caption">{content}</p>}
        </div>
      );
    }

    if (media_type === 'video' && safeSrc) {
      return (
        <div className="media-content">
          <video controls className="chat-media-video"><source src={safeSrc} /></video>
          {content && <p className="media-caption">{content}</p>}
        </div>
      );
    }

    if (media_type === 'document' && safeSrc) {
       return (
         <div className="media-content">
            <a href={safeSrc} target="_blank" rel="noreferrer" style={{color: '#4ec9b0', textDecoration: 'underline'}}>📄 Arquivo Recebido</a>
            {content && <p className="media-caption">{content}</p>}
         </div>
       );
    }
    return <p>{content}</p>;
  };

  // --- VARIÁVEIS DE RENDERIZAÇÃO ---
  const basicName = formatContactName(activeConversation.contact_name);
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
            <img src={finalAvatar} alt="Avatar" className="chat-avatar" onError={(e) => e.target.src = DEFAULT_AVATAR_URL}/>
            <div className="chat-header-info"><div className="chat-header-name">{basicName}</div></div>
        </div>
      </div>

      <div className="chat-messages" ref={chatContainerRef}>
        {/* Mostra o loading se estiver buscando mensagens */}
        {isLoadingMessages ? <div className="chat-placeholder">Carregando mensagens...</div> :
         /* Mostra o placeholder se não houver mensagens */
         messages.length === 0 ? <div className="chat-placeholder">Nenhuma mensagem nesta conversa.</div> :
         /* Renderiza as mensagens */
         messages.map((msg, i) => (
            <div key={msg.message_id || msg.id || i} className={`message-bubble-row message-${msg.sender === 'cliente' ? 'client' : 'seller'}`} onContextMenu={(e) => msg.sender === 'cliente' && handleMessageContextMenu(e, msg)}>
                <div className={`message-bubble message-bubble-${msg.sender === 'cliente' ? 'client' : 'seller'}`}>

                  {renderMessageContent(msg)}

                  <div className="message-metadata"><span className="message-timestamp">{formatMessageTimestamp(msg.timestamp)}</span></div>
                </div>
            </div>
         ))}
        <div ref={chatEndRef} />
      </div>

      {showScrollButton && <button className="scroll-to-bottom-btn" onClick={() => scrollToBottom('smooth')}><ScrollDownIcon /></button>}
      {!isCopilotOpen && !isMobile && (<div className="copilot-trigger-tab" onClick={onToggleCopilot} title="Abrir Copilot"><BrainTabIcon /><span className="tab-label">Copilot</span></div>)}

      <div className="chat-input-area seller-input">
        <form onSubmit={handleSellerSubmit} className="chat-form">
          <button type="button" className="icon-button"><AttachIcon /></button>
          <input type="text" value={sellerResponse} onChange={(e) => setSellerResponse(e.target.value)} placeholder="Mensagem" />
          <button type="submit" className="icon-button"><SendIcon /></button>
        </form>
      </div>

      {contextMenu.visible && <MessageContextMenu x={contextMenu.x} y={contextMenu.y} onAnalyze={handleAnalyzeFromMenu} onClose={() => setContextMenu({ visible: false, x: 0, y: 0, message: null })} />}

      {isProfileOpen && (
        <div className="profile-overlay" onClick={() => setIsProfileOpen(false)}>
            <div className="profile-glass-card" onClick={(e) => e.stopPropagation()}>
                <button className="close-profile-btn" onClick={() => setIsProfileOpen(false)}><CloseIcon /></button>
                {isLoadingProfile && !profileData ? <div className="spinner-dot" style={{margin: '50px auto'}}></div> : (
                   <>
                     <img src={finalAvatar} alt="Profile" className="profile-large-avatar" onError={(e) => e.target.src = DEFAULT_AVATAR_URL} />
                     <div className="profile-name">{finalName}{isBusiness && <span className="business-badge">Business</span>}</div>
                     <div className="profile-number">+{displayPhone}</div>
                     <div className="profile-info-grid">
                        <div className="info-item"><span className="info-label">Recado / Descrição</span><span className="info-value">{description}</span></div>
                        {email && <div className="info-item"><span className="info-label">Email</span><span className="info-value">{email}</span></div>}
                        {website && <div className="info-item"><span className="info-label">Site</span><a href={website} target="_blank" rel="noreferrer" className="info-value" style={{color: '#4ec9b0'}}>{website}</a></div>}
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
// frontend/src/components/CopilotPanel.js
import React, { useMemo, useState, useEffect } from 'react';
import { useChat } from '../context/ChatContext';
import VideoSuggestionCard from './VideoSuggestionCard';

// Ícones
const CloseIcon = () => <svg width="20" height="20" viewBox="0 0 24 24"><path fill="currentColor" d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" /></svg>;
// const CopyIcon = () => ... (Removido pois vamos usar o de enviar)
const SendPlaneIcon = () => <svg width="18" height="18" viewBox="0 0 24 24"><path fill="currentColor" d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" /></svg>;
const MagicIcon = () => <span>✨</span>;
// Ícone específico para o botão "Usar Sugestão" (Seta curva de resposta)
const ReplyIcon = () => <svg width="18" height="18" viewBox="0 0 24 24"><path fill="currentColor" d="M10 9V5l-7 7 7 7v-4.1c5 0 8.5 1.6 11 5.1-1-5-4-10-11-11z" /></svg>;


function CopilotPanel() {
  const {
    conversations, activeConversationId,
    suggestions, isCopilotLoading, lastAnalyzedMessage, queryType,
    clearSuggestions, handleToggleCopilot, handleInternalQuery,
    handleSendMessage // <--- 1. IMPORTAMOS A FUNÇÃO DE ENVIO AQUI
  } = useChat();

  const [internalInput, setInternalInput] = useState('');
  const [isExiting, setIsExiting] = useState(false);
  const [loadingText, setLoadingText] = useState('Consultando Cérebro...');

  React.useEffect(() => {
    if (!isCopilotLoading) return;

    const messages = [
      "Consultando Cérebro...",
      "Analisando o sentimento do cliente...",
      "Buscando melhores estratégias...",
      "Verificando histórico da conversa...",
      "Criando resposta persuasiva..."
    ];

    let i = 0;
    setLoadingText(messages[0]); // Reseta para a primeira

    const interval = setInterval(() => {
      i = (i + 1) % messages.length;
      setLoadingText(messages[i]);
    }, 2500); // Troca a cada 2.5 segundos

    return () => clearInterval(interval);
  }, [isCopilotLoading]);

  const activeChat = useMemo(() => {
    if (!conversations || !activeConversationId) return null;
    return conversations.find(c => c.id === activeConversationId);
  }, [conversations, activeConversationId]);

  const handleInternalSubmit = (event) => {
    event.preventDefault();
    if (!internalInput.trim()) return;
    handleInternalQuery(internalInput);
    setInternalInput('');
  };

  // --- 2. NOVA FUNÇÃO: Envia direto em vez de copiar ---

  const handleUseSuggestion = async (text) => {
    if (!text) return;

    // 1. Envia a mensagem imediatamente
    await handleSendMessage(text);

    // 2. Ativa a animação de saída
    setIsExiting(true);

    // 3. Aguarda o tempo da animação (400ms do CSS) antes de limpar os dados
    setTimeout(() => {
      clearSuggestions();
      setIsExiting(false); // Reseta o estado local
    }, 400);
  };

  if (!activeChat) return null;

  return (
    <div className="copilot-panel">

      {/* --- 1. HEADER (INPUT INTERNO) --- */}
      <div className="copilot-header">
        <div className="header-controls">
          <form onSubmit={handleInternalSubmit} className="ai-input-form glass-input">
            <input
              type="text"
              placeholder="Pergunte ao Cérebro..."
              value={internalInput}
              onChange={(event) => setInternalInput(event.target.value)}
              className="ai-input"
            />
            <button type="submit" className="ai-send-btn" disabled={isCopilotLoading}>
              <SendPlaneIcon />
            </button>
          </form>
          <button className="icon-button close-btn" onClick={handleToggleCopilot}>
            <CloseIcon />
          </button>
        </div>
      </div>

      {/* --- 2. CORPO --- */}
      <div className="copilot-body">

        {/* ANIMAÇÃO DE CARREGAMENTO */}
        {isCopilotLoading && (
          <div className="copilot-loading">
            <div className="ai-orb"></div>
            <p style={{ minHeight: '1.5em', transition: 'all 0.3s' }}>
              {loadingText}
            </p>
          </div>
        )}

        {!isCopilotLoading && !suggestions && (
          <div className="copilot-loading">
            <div className="empty-icon"><MagicIcon /></div>
            <p>Selecione uma mensagem ou digite acima para ativar a IA.</p>
          </div>
        )}

        {!isCopilotLoading && suggestions && (
          <div className="suggestion-wrapper fade-in">

            {/* Contexto */}
            <div className="context-badge">
              {queryType === 'analysis' ? 'Análise de Cliente' : 'Resposta Interna'}
            </div>

            {lastAnalyzedMessage && queryType === 'analysis' && (
              <p className="context-text">"{lastAnalyzedMessage}"</p>
            )}

            {/* CARD LIQUID GLASS - Resposta Imediata */}
            {suggestions.immediate_answer && (
              <div className="glass-card main-card">
                <div className="card-header">
                  <h4>Sugestão</h4>
                </div>
                <div className="card-content">
                  {suggestions.immediate_answer}
                </div>

                {/* 3. BOTÃO ALTERADO: Usar Sugestão */}
                <button
                  className="action-btn primary-glass-btn"
                  onClick={() => handleUseSuggestion(suggestions.immediate_answer)}
                >
                  <ReplyIcon /> Usar Sugestão
                </button>
              </div>
            )}

            {/* Sugestão de Vídeo */}
            {suggestions.video && (
              <VideoSuggestionCard video={suggestions.video} />
            )}

            {/* Próximos Passos */}
            {suggestions.follow_up_options?.map((option, index) => (
              <div key={index} className="glass-card secondary-card">
                <h4>🎯 Próximo Passo</h4>
                <p>{option.text}</p>
                {/* O botão foi removido daqui, tornando o card apenas informativo */}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* --- 3. FOOTER FIXO --- */}
      <div className="copilot-footer">
        <button className="clear-btn" onClick={clearSuggestions}>
          Limpar Histórico
        </button>
      </div>
    </div>
  );
}

export default CopilotPanel;
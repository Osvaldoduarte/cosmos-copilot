// Em frontend/src/components/CopilotPanel.js
// (SUBSTITUA o conteúdo deste arquivo)

import React, { useState, useMemo } from 'react';
import { useChat } from '../context/ChatContext';
// 💡 REMOVIDO: import { Droppable } from 'react-beautiful-dnd';

// --- Ícones ---
const ClearSuggestionsIcon = () => (<svg width="16" height="16" viewBox="0 0 24 24"><path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" stroke="currentColor" strokeWidth="2" fill="none"/></svg>);
// 💡 REMOVIDO: const DragDropIcon = () => (...)
// --- Fim dos Ícones ---


function CopilotPanel() {
  const [privateQuery, setPrivateQuery] = useState('');

  const {
    activeConversationId,
    suggestionsByConvo,
    handlePrivateSuggestionRequest,
    handleUseSuggestion,
    handleDeleteSuggestion,
    handleClearSuggestions,
  } = useChat(); // 💡 handleMessageDrop removido daqui

  const isChatLoading = false;
  const chatError = null;

  const activeSuggestions = useMemo(() => {
    if (!activeConversationId) return [];
    return suggestionsByConvo[activeConversationId]?.suggestions || [];
  }, [activeConversationId, suggestionsByConvo]);

  const activeVideo = useMemo(() => {
    if (!activeConversationId) return null;
    return suggestionsByConvo[activeConversationId]?.video || null;
  }, [activeConversationId, suggestionsByConvo]);

  const handlePrivateQuerySubmit = (e) => {
    e.preventDefault();
    if (privateQuery.trim()) {
      handlePrivateSuggestionRequest(privateQuery);
      setPrivateQuery('');
    }
  };

  return (
    <div className="copilot-panel">
      {/* --- CABEÇALHO --- */}
      <div className="copilot-header">
        <h4>Copilot (IA)</h4>
        <button
          className="clear-suggestions-btn"
          onClick={() => handleClearSuggestions()}
        >
          <ClearSuggestionsIcon />
        </button>
      </div>

      {/* --- INPUT PRIVADO --- */}
<div className="copilot-input">
        {/* 💡 Classe adicionada ao formulário */}
        <form onSubmit={handlePrivateQuerySubmit} className="private-query-form">
          <input
            type="text"
            // ...
          />
          <button type="submit">Enviar</button>
        </form>

        {/* 💡 CORREÇÃO: Removida a área de Drag-and-Drop */}
        {/* <div className="drag-drop-prompt"> ... </div> */}
      </div>

      {/* --- LISTA DE SUGESTÕES --- */}
      <div className="copilot-output">
        {isChatLoading && <div className="loading-placeholder">Gerando sugestão...</div>}
        {chatError && <div className="error-message">{chatError}</div>}

        {/* <VideoSuggestionCard video={activeVideo} /> (Seu componente) */}

        <div className="suggestions-list">
          {activeSuggestions.length > 0 ? (
            activeSuggestions.map((sug) => (
              <div key={sug.id} className="suggestion-card">
                <p>{sug.text}</p>
                <button onClick={() => handleUseSuggestion(sug.id, sug.text)}>
                  Usar
                </button>
                <button onClick={() => handleDeleteSuggestion(sug.id)}>
                  X
                </button>
              </div>
            ))
          ) : (
            !isChatLoading && (
              <div className="empty-placeholder">
                Use o clique direito em uma<br/>
                mensagem do cliente para<br/>
                enviar à IA.
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}

export default CopilotPanel;
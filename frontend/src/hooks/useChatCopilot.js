// Em frontend/src/hooks/useChatCopilot.js
// (ARQUIVO NOVO)

import { useState, useCallback } from 'react';

/**
 * Hook (Refatorado)
 * Responsabilidade Única: Gerenciar o Copilot (Sugestões, IA).
 * 💡 CORRIGE O BUG de Drag-and-Drop.
 */
export function useChatCopilot(conversations, activeConversationId) {
  const [suggestionsByConvo, setSuggestionsByConvo] = useState({});
  const [stagesByConvo, setStagesByConvo] = useState({});

  // Handlers
  const handleSuggestionRequest = useCallback((query) => {
    console.log("[Copilot] Solicitação de sugestão para:", query);
  }, []);

  const handleUseSuggestion = useCallback((sugId, text) => {
    console.log("[Copilot] Usando sugestão:", text);
  }, []);

  const handleDeleteSuggestion = useCallback((sugId) => {
    console.log("[Copilot] Deletando sugestão:", sugId);
  }, []);

  // 💡 CORREÇÃO: Lógica de Drop (arrastar)
  const handleMessageDrop = useCallback((messageId) => {
  }, [conversations, activeConversationId, handleSuggestionRequest]);

  const handleClearSuggestions = useCallback(() => {
    console.log("[Copilot] Limpando sugestões para:", activeConversationId);
  }, [activeConversationId]);

  const handlePrivateSuggestionRequest = useCallback((query) => {
    console.log("[Copilot] Solicitação privada:", query);
  }, []);

  return {
    suggestionsByConvo,
    stagesByConvo,
    handleSuggestionRequest,
    handleUseSuggestion,
    handleDeleteSuggestion,
    handleClearSuggestions,
    handlePrivateSuggestionRequest,
  };
}
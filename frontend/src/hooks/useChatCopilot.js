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
    if (!activeConversationId || !conversations[activeConversationId]) {
      console.error("[DragDrop] Drop ocorreu sem conversa ativa.");
      return;
    }

    // Procura a mensagem no cache
    const message = conversations[activeConversationId].messages.find(
      (msg) => String(msg.id) === String(messageId)
    );

    if (message && message.content) {
      console.log(`[DragDrop] Mensagem ${messageId} solta. Analisando: "${message.content}"`);
      handleSuggestionRequest(message.content);
    } else {
      console.error(`[DragDrop] Mensagem com ID ${messageId} não encontrada no cache.`);
    }
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
    handleMessageDrop, // <-- Agora está funcional
    handleClearSuggestions,
    handlePrivateSuggestionRequest,
  };
}
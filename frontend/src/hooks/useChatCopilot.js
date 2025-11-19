// Em frontend/src/hooks/useChatCopilot.js
import { useCallback } from 'react'; // Removemos useState
import api from '../services/api';

// Agora recebe 'updateCopilotState' como parâmetro
export function useChatCopilot(conversations, activeConversationId, setIsCopilotOpen, updateCopilotState) {

  // --- LEITURA DO ESTADO (Vem da conversa ativa) ---
  const activeChat = activeConversationId ? conversations[activeConversationId] : null;
  const copilotState = activeChat?.copilot || {};

  // Se não tiver nada salvo, usamos valores padrão
  const suggestions = copilotState.suggestions || null;
  const lastAnalyzedMessage = copilotState.lastAnalyzedMessage || null;
  const queryType = copilotState.queryType || 'analysis';
  const isCopilotLoading = copilotState.isLoading || false;

  // --- AÇÕES (Gravam na conversa ativa) ---

  const clearSuggestions = useCallback(() => {
    if (!activeConversationId) return;
    updateCopilotState(activeConversationId, {
        suggestions: null,
        lastAnalyzedMessage: null,
        queryType: 'analysis',
        isLoading: false
    });
  }, [activeConversationId, updateCopilotState]);

  const _sendToAi = async (text, isPrivate) => {
    if (!activeConversationId) return;

    if (setIsCopilotOpen) {
        setIsCopilotOpen(true);
    }

    // 1. Define Loading no estado da conversa
    updateCopilotState(activeConversationId, {
        isLoading: true,
        suggestions: null, // Limpa anterior enquanto carrega
        lastAnalyzedMessage: isPrivate ? null : text // Salva msg se for análise
    });

    try {
      const response = await api.post('/copilot/analyze', {
        contact_id: activeConversationId,
        query: text,
        is_private: isPrivate
      });

      if (response.data && response.data.status === 'success') {
        // 2. Salva Sucesso no estado da conversa
        updateCopilotState(activeConversationId, {
            suggestions: response.data.suggestions,
            queryType: isPrivate ? 'internal' : 'analysis',
            isLoading: false
        });
      } else {
        updateCopilotState(activeConversationId, {
            suggestions: { immediate_answer: "Não foi possível gerar uma resposta." },
            isLoading: false
        });
      }
    } catch (error) {
      console.error("❌ Erro Copilot:", error);
      updateCopilotState(activeConversationId, {
        suggestions: { immediate_answer: "Erro de conexão com a IA." },
        isLoading: false
      });
    }
  };

  const handleSuggestionRequest = useCallback((msg) => {
    _sendToAi(msg, false);
  }, [activeConversationId, updateCopilotState]); // Adicione updateCopilotState nas deps

  const handleInternalQuery = useCallback((question) => {
    _sendToAi(question, true);
  }, [activeConversationId, updateCopilotState]);

  return {
    isCopilotLoading,
    suggestions,
    lastAnalyzedMessage,
    queryType,
    handleSuggestionRequest,
    handleInternalQuery,
    clearSuggestions
  };
}
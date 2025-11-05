// Em frontend/src/hooks/useChatData.js
// (ARQUIVO NOVO)

import { useState, useEffect, useCallback, useMemo } from 'react';
import api from '../services/api';

/**
 * Hook (Refatorado)
 * Responsabilidade Única: Gerenciar o estado dos dados,
 * o polling da lista e o cache de mensagens.
 */
export function useChatData(token, instanceConnected) {
  const [conversations, setConversations] = useState({});
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [isLoading, setIsLoading] = useState(true); // Loading inicial da lista
  const [isLoadingMessages, setIsLoadingMessages] = useState(false); // Loading de mensagens
  const [error, setError] = useState('');

  // --- DADOS DERIVADOS (useMemo) ---
  const unreadCount = useMemo(() => {
    return Object.values(conversations).reduce((count, convo) => {
      return convo.unread ? count + 1 : count;
    }, 0);
  }, [conversations]);

  const activeMessages = useMemo(() => {
    if (!activeConversationId) return [];
    return conversations[activeConversationId]?.messages || [];
  }, [activeConversationId, conversations]);

  // --- AÇÕES DE DADOS (useCallback) ---

  // 1. Polling (Corrigido o loop infinito)
  const fetchConversations = useCallback(async () => {
    if (!token) return;
    try {
      const { data } = await api.get('/conversations/');
      if (data && data.status === 'success') {
        // Usa a forma funcional do setter (evita loop)
        setConversations(prevConvos => {
          const newConvosMap = data.conversations.reduce((acc, convo) => {
            const existingMessages = prevConvos[convo.id]?.messages || [];
            acc[convo.id] = { ...convo, messages: existingMessages };
            return acc;
          }, {});
          return newConvosMap;
        });
      }
    } catch (err) {
      console.error("[fetchConversations] Erro:", err.response ? err.response.data : err.message);
      setError('Falha ao buscar conversas.');
    } finally {
      setIsLoading(false);
    }
  }, [token]); // Removida a dependência 'conversations'

  // 2. Seleção de Chat (com Cache)
  const handleConversationSelect = useCallback(async (convoId) => {
    if (!convoId || convoId === activeConversationId) return;

    setActiveConversationId(convoId);

    // 💡 Usa 'setConversations' para ler o estado mais recente
    setConversations(prevConvos => {
      const hasMessages = prevConvos[convoId]?.messages?.length > 0;

      // CACHE HIT
      if (hasMessages) {
        setIsLoadingMessages(false);
        api.post(`/conversations/${convoId}/mark-read`); // (em background)
        return prevConvos; // Retorna o estado sem mudanças
      }

      // CACHE MISS
      setIsLoadingMessages(true);

      // Busca assíncrona (não pode estar dentro do setter)
      (async () => {
        try {
          api.post(`/conversations/${convoId}/mark-read`);
          const { data } = await api.get(`/conversations/${convoId}/messages`);
          const fetchedMessages = data || [];

          // Salva no cache
          setConversations(pConvos => ({
              ...pConvos,
              [convoId]: { ...pConvos[convoId], messages: fetchedMessages }
          }));
        } catch (err) {
          console.error(`[handleConversationSelect] Erro ao buscar mensagens para ${convoId}:`, err);
          setError('Falha ao carregar mensagens.');
        } finally {
          setIsLoadingMessages(false);
        }
      })();

      return prevConvos; // Retorna o estado original (será atualizado pelo async)
    });
  }, [activeConversationId]); // Removido 'conversations'

  // 3. Iniciar Nova Conversa
  const handleStartConversation = useCallback(async (number, message) => {
    try {
      await api.post('/new-conversation', {
        recipient_number: number,
        initial_message: message,
      });
      setTimeout(fetchConversations, 1000);
      return true;
    } catch (err) {
      console.error("Erro ao iniciar conversa:", err);
      return false;
    }
  }, [fetchConversations]);

  // --- EFEITO DE POLLING ---
  useEffect(() => {
    let intervalId = null;
    if (token && instanceConnected) {
      fetchConversations();
      intervalId = setInterval(fetchConversations, 5000);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [token, instanceConnected, fetchConversations]);

  // --- RETORNO DO HOOK DE DADOS ---
  return {
    conversations,
    activeConversationId,
    activeMessages,
    isLoading,
    isLoadingMessages,
    error,
    unreadCount,
    setActiveConversationId, // Exposto para o useChatUI
    handleConversationSelect,
    handleStartConversation,
  };
}
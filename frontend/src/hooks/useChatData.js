// Em frontend/src/hooks/useChatData.js
import { useState, useEffect, useCallback, useMemo } from 'react';
import api from '../services/api';

export function useChatData(token, instanceConnected) {
  const [conversations, setConversations] = useState({});
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [error, setError] = useState('');

  // --- DADOS DERIVADOS ---
  const unreadCount = useMemo(() => {
    return Object.values(conversations).reduce((count, convo) => {
      return convo.unread ? count + 1 : count;
    }, 0);
  }, [conversations]);

  const activeMessages = useMemo(() => {
    if (!activeConversationId) return [];
    return conversations[activeConversationId]?.messages || [];
  }, [activeConversationId, conversations]);

  // --- AÇÕES ---

  const fetchConversations = useCallback(async () => {
    if (!token) return;
    try {
      const { data } = await api.get('/conversations/');
      if (data && data.status === 'success') {
        setConversations(prevConvos => {
          const newConvosMap = data.conversations.reduce((acc, convo) => {
            // PRESERVA O ESTADO DO COPILOT (Se já existir)
            const existingCopilot = prevConvos[convo.id]?.copilot || null;
            const existingMessages = prevConvos[convo.id]?.messages || [];

            // ✨ CORREÇÃO: Normaliza o Avatar
            // Procura em vários campos possíveis que o backend possa estar enviando
            const normalizedAvatar =
                convo.avatar_url ||
                convo.profile_picture_url ||
                convo.profilePictureUrl ||
                convo.pic ||
                null;

            acc[convo.id] = {
                ...convo,
                avatar_url: normalizedAvatar, // Garante que o campo 'avatar_url' sempre exista
                messages: existingMessages,
                copilot: existingCopilot
            };
            return acc;
          }, {});
          return newConvosMap;
        });
      }
    } catch (err) {
      console.error("[fetchConversations] Erro:", err);
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  const handleConversationSelect = useCallback(async (convoId) => {
    if (!convoId || convoId === activeConversationId) return;
    setActiveConversationId(convoId);

    setConversations(prevConvos => {
      const hasMessages = prevConvos[convoId]?.messages?.length > 0;

      if (hasMessages) {
        setIsLoadingMessages(false);
        api.post(`/conversations/${convoId}/mark-read`).catch(() => {});
        return prevConvos;
      }

      setIsLoadingMessages(true);

      (async () => {
        try {
          api.post(`/conversations/${convoId}/mark-read`).catch(() => {});
          const { data } = await api.get(`/conversations/${convoId}/messages`);
          const fetchedMessages = (data || []).map(msg => {
              const isSeller = msg.sender === 'me' || msg.sender === 'vendedor' || msg.fromMe === true;
              return {
                  ...msg,
                  media_type: msg.media_type || 'text',
                  sender: isSeller ? 'vendedor' : 'cliente'
              };
          });

          setConversations(pConvos => ({
              ...pConvos,
              [convoId]: {
                ...pConvos[convoId],
                messages: fetchedMessages,
                unread: 0
              }
          }));
        } catch (err) {
          console.error(`Erro ao buscar mensagens:`, err);
          setError('Falha ao carregar mensagens.');
        } finally {
          setIsLoadingMessages(false);
        }
      })();

      return { ...prevConvos, [convoId]: { ...prevConvos[convoId], unread: 0 } };
    });
  }, [activeConversationId]);

  const handleStartConversation = useCallback(async (number, message) => {
    try {
      await api.post('/new-conversation', {
        recipient_number: number,
        initial_message: message,
      });
      setTimeout(fetchConversations, 500);
      return true;
    } catch (err) {
      console.error("Erro ao iniciar conversa:", err);
      return false;
    }
  }, [fetchConversations]);

  const handleSendMessage = useCallback(async (text) => {
    if (!activeConversationId || !text.trim()) return false;

    const tempId = `temp-${Date.now()}`;
    const newMessageObj = {
        id: tempId,
        contact_id: activeConversationId,
        content: text,
        sender: 'vendedor',
        timestamp: Math.floor(Date.now() / 1000),
        status: 'sending',
        media_type: 'text',
    };

    setConversations(prev => {
        const currentConvo = prev[activeConversationId];
        if (!currentConvo) return prev;
        const newMessages = [...(currentConvo.messages || []), newMessageObj];
        return {
            ...prev,
            [activeConversationId]: {
                ...currentConvo,
                lastMessage: text,
                timestamp: Math.floor(Date.now() / 1000),
                messages: newMessages
            }
        };
    });

    try {
        const response = await api.post('/evolution/message/send', {
            contact_id: activeConversationId,
            text: text
        });
        const realMessageId = response.data?.message_id || tempId;
        setConversations(prev => {
            const currentConvo = prev[activeConversationId];
            if (!currentConvo) return prev;
            const updatedMessages = currentConvo.messages.map(msg =>
                msg.id === tempId ? { ...msg, id: realMessageId, status: 'delivered' } : msg
            );
            return {
                ...prev,
                [activeConversationId]: { ...currentConvo, messages: updatedMessages }
            };
        });
        return true;
    } catch (err) {
        console.error("Erro ao enviar mensagem:", err);
        setConversations(prev => {
            const currentConvo = prev[activeConversationId];
            if (!currentConvo) return prev;
            const updatedMessages = currentConvo.messages.map(msg =>
                msg.id === tempId ? { ...msg, status: 'failed' } : msg
            );
            return {
                ...prev,
                [activeConversationId]: { ...currentConvo, messages: updatedMessages }
            };
        });
        return false;
    }
  }, [activeConversationId]);

  const updateCopilotState = useCallback((convoId, newState) => {
    setConversations(prev => {
      const convo = prev[convoId];
      if (!convo) return prev;
      return {
        ...prev,
        [convoId]: {
          ...convo,
          copilot: { ...(convo.copilot || {}), ...newState }
        }
      };
    });
  }, []);

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

  return {
    conversations,
    activeConversationId,
    activeMessages,
    isLoading,
    isLoadingMessages,
    error,
    unreadCount,
    setActiveConversationId,
    handleConversationSelect,
    handleStartConversation,
    handleSendMessage,
    updateCopilotState,
  };
}
import React, { createContext, useState, useContext, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../hooks/useAuth';

const ChatContext = createContext();

export const ChatProvider = ({ children }) => {
    // --- ESTADOS ---
    const [conversations, setConversations] = useState([]);
    const [activeConversationId, setActiveConversationId] = useState(null);
    const [messages, setMessages] = useState([]);
    // Estados de UI
    const [isCopilotOpen, setIsCopilotOpen] = useState(false);
    const [isModalOpen, setIsModalOpen] = useState(false);

    // --- CONFIGURAÇÃO ---
    const { token, handleLogout } = useAuth();
    const API_BASE_URL = 'http://localhost:8000';
    const WS_URL = 'ws://localhost:8000/ws';

    // Ref para acesso dentro do WebSocket sem recriar conexão
    const activeConversationIdRef = useRef(activeConversationId);
    useEffect(() => {
        activeConversationIdRef.current = activeConversationId;
    }, [activeConversationId]);

    // --- FUNÇÕES DE INTERFACE ---
    const handleToggleCopilot = () => setIsCopilotOpen(prev => !prev);
    const handleCloseModal = () => setIsModalOpen(false);

    const handleBackToList = () => {
        setActiveConversationId(null);
        setMessages([]);
    };

    // --- 1. SELEÇÃO DE CONVERSA (A função que faltava!) ---
    const handleConversationSelect = (conversationId) => {
        setActiveConversationId(conversationId);
        // Opcional: Aqui você pode chamar uma rota para marcar como lida no backend
        // markAsRead(conversationId);
    };

    // --- 2. BUSCAR CONVERSAS (Lista Lateral) ---
    const fetchConversations = useCallback(async () => {
        if (!token) return;
        try {
            const response = await fetch(`${API_BASE_URL}/conversations`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.status === 401) {
                handleLogout();
                return;
            }
            if (response.ok) {
                const data = await response.json();
                const lista = data.conversations || data || [];
                setConversations(lista);
            }
        } catch (error) {
            console.error("Erro ao buscar conversas:", error);
        }
    }, [token, handleLogout]);

    // Polling da lista (Mantido como fallback)
    useEffect(() => {
        fetchConversations();
        const interval = setInterval(fetchConversations, 10000); // Aumentado para 10s
        return () => clearInterval(interval);
    }, [fetchConversations]);

    // --- 3. BUSCAR MENSAGENS (Chat Aberto) ---
    const fetchMessages = useCallback(async (conversationId) => {
        if (!conversationId || !token) return;
        try {
            const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/messages`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.status === 401) {
                handleLogout();
                return;
            }
            if (response.ok) {
                const data = await response.json();
                // Proteção para garantir array
                setMessages(Array.isArray(data) ? data : (data.messages || []));
            } else {
                setMessages([]);
            }
        } catch (error) {
            console.error("Erro ao buscar mensagens:", error);
            setMessages([]);
        }
    }, [token, handleLogout]);

    // Dispara busca quando muda a conversa ativa
    useEffect(() => {
        if (activeConversationId) {
            fetchMessages(activeConversationId);
            // Polling de mensagens reduzido, pois agora temos WebSocket
            const msgInterval = setInterval(() => fetchMessages(activeConversationId), 10000);
            return () => clearInterval(msgInterval);
        }
    }, [activeConversationId, fetchMessages]);

    // --- WEBSOCKET (REAL-TIME) ---
    useEffect(() => {
        let ws;
        try {
            ws = new WebSocket(WS_URL);

            ws.onopen = () => {
                console.log('🟢 WebSocket Conectado');
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'new_message') {
                        const { conversation_id, message } = data;
                        const currentActiveId = activeConversationIdRef.current;

                        // 1. Atualiza Mensagens se estiver na conversa ativa
                        if (currentActiveId === conversation_id) {
                            setMessages(prev => {
                                // Evita duplicatas
                                if (prev.some(m => m.message_id === message.message_id)) return prev;
                                return [...prev, message];
                            });
                        }

                        // 2. Atualiza Lista de Conversas
                        setConversations(prev => {
                            const index = prev.findIndex(c => c.id === conversation_id);

                            // Se a conversa não existe na lista, busca tudo de novo
                            if (index === -1) {
                                fetchConversations();
                                return prev;
                            }

                            const updated = [...prev];
                            const conv = { ...updated[index] };

                            // Atualiza dados da prévia
                            conv.lastMessage = message.content;
                            conv.lastUpdated = message.timestamp * 1000;

                            // Marca como não lida se não estivermos nela e for do cliente
                            if (message.sender === 'cliente' && currentActiveId !== conversation_id) {
                                conv.unread = true;
                                conv.unreadCount = (conv.unreadCount || 0) + 1;
                            } else if (currentActiveId === conversation_id) {
                                // Se estivermos nela, garante que não fique unread
                                conv.unread = false;
                                conv.unreadCount = 0;
                            }

                            updated[index] = conv;
                            // Reordena por data
                            updated.sort((a, b) => b.lastUpdated - a.lastUpdated);
                            return updated;
                        });
                    }
                } catch (e) {
                    console.error("Erro no processamento do WS:", e);
                }
            };

            ws.onclose = () => {
                console.log('🔴 WebSocket Desconectado');
                // Reconexão simples poderia ser implementada aqui
            };
        } catch (e) {
            console.error("Erro ao criar WebSocket:", e);
        }

        return () => {
            if (ws) ws.close();
        };
    }, [fetchConversations]); // Executa apenas na montagem (e se fetchConversations mudar, o que é raro)

    // --- 4. ENVIAR MENSAGEM ---
    const handleSendMessage = async (messageData) => {
        if (!activeConversationId) return;
        try {
            const response = await fetch(`${API_BASE_URL}/messages/send`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    conversation_id: activeConversationId,
                    message_text: messageData
                })
            });
            if (response.status === 401) {
                handleLogout();
                return false;
            }
            if (response.ok) {
                // Não precisamos chamar fetchMessages aqui se o WebSocket estiver funcionando,
                // mas deixamos por segurança ou para feedback imediato da UI (otimista)
                // fetchMessages(activeConversationId); 
                // fetchConversations();
                return true;
            }
        } catch (error) {
            console.error("Erro ao enviar mensagem:", error);
        }
        return false;
    };

    const handleStartConversation = async (number, message) => {
        try {
            const response = await fetch(`${API_BASE_URL}/conversations/start_new`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ recipient_number: number, initial_message: message })
            });
            if (response.status === 401) {
                handleLogout();
                return false;
            }
            if (response.ok) {
                fetchConversations();
                return true;
            }
        } catch (error) {
            console.error("Erro ao iniciar conversa:", error);
        }
        return false;
    };

    // --- 5. COPILOT / IA ---
    const [suggestions, setSuggestions] = useState(null);
    const [isCopilotLoading, setIsCopilotLoading] = useState(false);
    const [lastAnalyzedMessage, setLastAnalyzedMessage] = useState(null);
    const [queryType, setQueryType] = useState('analysis');

    const clearSuggestions = () => {
        setSuggestions(null);
        setLastAnalyzedMessage(null);
    };

    const handleInternalQuery = async (query) => {
        if (!query) return;
        setIsCopilotLoading(true);
        setQueryType('internal');
        setSuggestions(null);

        try {
            const response = await fetch(`${API_BASE_URL}/ai/generate_suggestion`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ conversation_id: activeConversationId, query: query, type: 'internal' })
            });
            if (response.status === 401) {
                handleLogout();
                return;
            }
            const data = await response.json();
            if (data.status === 'success') {
                setSuggestions(data.suggestions);
            }
        } catch (e) {
            console.error(e);
        } finally {
            setIsCopilotLoading(false);
        }
    };

    const handleSuggestionRequest = async (text, conversationId) => {
        setIsCopilotLoading(true);
        setQueryType('analysis');
        setLastAnalyzedMessage(text);
        setSuggestions(null);
        // Open copilot if closed
        if (!isCopilotOpen) setIsCopilotOpen(true);

        try {
            const response = await fetch(`${API_BASE_URL}/ai/generate_suggestion`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ conversation_id: conversationId, query: text, type: 'analysis' })
            });
            if (response.status === 401) {
                handleLogout();
                return;
            }
            const data = await response.json();
            if (data.status === 'success') {
                setSuggestions(data.suggestions);
            }
        } catch (e) {
            console.error(e);
        } finally {
            setIsCopilotLoading(false);
        }
    };

    // Objeto final exportado
    const value = {
        conversations,
        activeConversationId,
        setActiveConversationId,
        messages,
        setMessages,
        isCopilotOpen,
        setIsCopilotOpen,
        handleToggleCopilot,
        isModalOpen,
        setIsModalOpen,
        handleCloseModal,
        handleBackToList,
        handleStartConversation,
        handleConversationSelect,
        handleSendMessage,
        fetchConversations,
        fetchMessages,
        // Copilot Exports
        suggestions,
        isCopilotLoading,
        lastAnalyzedMessage,
        queryType,
        clearSuggestions,
        handleInternalQuery,
        handleSuggestionRequest
    };

    return (
        <ChatContext.Provider value={value}>
            {children}
        </ChatContext.Provider>
    );
};

export const useChat = () => {
    const context = useContext(ChatContext);
    if (!context) throw new Error('useChat deve ser usado dentro de um ChatProvider');
    return context;
};
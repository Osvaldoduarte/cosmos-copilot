import React, { createContext, useState, useContext, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../hooks/useAuth';

const ChatContext = createContext();

// 🎯 Utility: Determina o nome de exibição baseado em prioridades
export const getDisplayName = (conversation) => {
    if (!conversation) return '';

    // 1ª Prioridade: Nome customizado pelo usuário
    if (conversation.custom_name) return conversation.custom_name;

    // 2ª Prioridade: Nome do WhatsApp (pushName)
    if (conversation.whatsapp_name) return conversation.whatsapp_name;

    // 3ª Prioridade (fallback): Número formatado
    const number = conversation.id ? conversation.id.split('@')[0] : conversation.phone_number;
    return number || 'Desconhecido';
};


export const ChatProvider = ({ children }) => {
    // --- ESTADOS PRINCIPAIS ---
    const [conversations, setConversations] = useState([]);
    const [activeConversationId, setActiveConversationId] = useState(null);
    const [messages, setMessages] = useState([]);

    // Estados UI
    const [isCopilotOpen, setIsCopilotOpen] = useState(false);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);

    // Listener de resize para isMobile
    useEffect(() => {
        const handleResize = () => setIsMobile(window.innerWidth <= 768);
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    // --- ESTADOS DO COPILOT (IA) ---
    const [suggestions, setSuggestions] = useState(null);
    const [isCopilotLoading, setIsCopilotLoading] = useState(false);
    const [lastAnalyzedMessage, setLastAnalyzedMessage] = useState(null);
    const [queryType, setQueryType] = useState('analysis'); // 'analysis' ou 'internal'

    // --- CONFIG ---
    const { token, handleLogout } = useAuth();
    const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
    const WS_URL = API_BASE_URL.replace(/^http/, 'ws') + '/ws';

    // Derivados
    const currentChat = conversations.find(c => c.id === activeConversationId) || null;
    const activeConversationIdRef = useRef(activeConversationId);
    const wsRef = useRef(null);

    useEffect(() => { activeConversationIdRef.current = activeConversationId; }, [activeConversationId]);

    // --- 1. FUNÇÕES DO COPILOT ---

    const clearSuggestions = useCallback(() => {
        setSuggestions(null);
        setLastAnalyzedMessage(null);
        setQueryType('analysis');
    }, []);

    // Ação: Analisar mensagem do cliente (Botão direito ou Automático)
    const handleSuggestionRequest = async (text, conversationId) => {
        if (!text) return;
        setIsCopilotLoading(true);
        setQueryType('analysis');
        setLastAnalyzedMessage(text);
        setSuggestions(null);

        if (!isCopilotOpen) setIsCopilotOpen(true);

        try {
            // Rota do backend que criamos no main.py
            const response = await fetch(`${API_BASE_URL}/ai/generate_suggestion`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ conversation_id: conversationId, query: text, type: 'analysis' })
            });
            const data = await response.json();
            if (data.status === 'success') setSuggestions(data.suggestions);
        } catch (e) { console.error(e); }
        finally { setIsCopilotLoading(false); }
    };

    // Ação: Pergunta interna (Input do Copilot)
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
            const data = await response.json();
            if (data.status === 'success') setSuggestions(data.suggestions);
        } catch (e) { console.error(e); }
        finally { setIsCopilotLoading(false); }
    };

    // --- 2. LÓGICA DE CHAT (WebSocket, Fetch, Send) ---
    // (Código mantido da versão anterior que já estava funcionando)

    const fetchConversations = useCallback(async () => {
        if (!token) return;
        try {
            const response = await fetch(`${API_BASE_URL}/conversations`, { headers: { 'Authorization': `Bearer ${token}` } });
            if (response.status === 401) { handleLogout(); return; }
            if (response.ok) {
                const data = await response.json();
                setConversations(data.conversations || []);
            }
        } catch (error) { console.error("Erro conversas:", error); }
    }, [token, API_BASE_URL, handleLogout]);

    useEffect(() => {
        fetchConversations();
        const interval = setInterval(fetchConversations, 30000);
        return () => clearInterval(interval);
    }, [fetchConversations]);

    // 🚀 Cache de mensagens para evitar re-fetch desnecessário
    const messagesCache = useRef(new Map());

    // Carrega cache do localStorage ao iniciar
    useEffect(() => {
        try {
            const cached = localStorage.getItem('chat_messages_cache');
            if (cached) {
                const parsed = JSON.parse(cached);
                messagesCache.current = new Map(Object.entries(parsed));
                console.log(`📦 Cache restaurado: ${messagesCache.current.size} conversas`);
            }
        } catch (e) { console.error("Erro ao restaurar cache:", e); }
    }, []);

    const saveCacheToStorage = () => {
        try {
            const obj = Object.fromEntries(messagesCache.current);
            localStorage.setItem('chat_messages_cache', JSON.stringify(obj));
        } catch (e) { console.error("Erro ao salvar cache:", e); }
    };

    const fetchMessages = useCallback(async (conversationId) => {
        if (!conversationId || !token) return;

        // 🚀 Verifica cache primeiro
        if (messagesCache.current.has(conversationId)) {
            console.log(`📦 Usando cache para ${conversationId}`);
            setMessages(messagesCache.current.get(conversationId));
            // Background refresh (opcional, para garantir consistência)
            // return; 
        }

        try {
            console.log(`🔄 Buscando mensagens do servidor para ${conversationId}`);
            const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/messages`, { headers: { 'Authorization': `Bearer ${token}` } });
            if (response.ok) {
                const data = await response.json();
                const msgs = Array.isArray(data) ? data : (data.messages || []);

                // Se o cache já tinha mensagens e a API retornou vazio (erro?), mantém o cache
                if (msgs.length === 0 && messagesCache.current.has(conversationId)) {
                    console.warn("API retornou vazio, mantendo cache.");
                    return;
                }

                setMessages(msgs);
                // Salva no cache e no storage
                messagesCache.current.set(conversationId, msgs);
                saveCacheToStorage();
            } else {
                if (!messagesCache.current.has(conversationId)) setMessages([]);
            }
        } catch (error) {
            if (!messagesCache.current.has(conversationId)) setMessages([]);
        }
    }, [token, API_BASE_URL]);

    useEffect(() => { if (activeConversationId) fetchMessages(activeConversationId); }, [activeConversationId, fetchMessages]);

    // WebSocket Connection (Otimizado)
    useEffect(() => {
        if (!token) return;
        if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) return;

        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onopen = () => console.log('🟢 WS Conectado');
        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                // 👍 Processar reações
                if (data.type === 'message_reaction') {
                    const { conversation_id, message_id, reaction, from } = data;
                    if (activeConversationIdRef.current === conversation_id) {
                        setMessages(prev => prev.map(m => {
                            if (m.message_id === message_id) {
                                const reactions = m.reactions || [];
                                // Remove reação anterior da mesma pessoa
                                const filtered = reactions.filter(r => r.from !== from);
                                // Adiciona nova reação (se não for vazia)
                                if (reaction) {
                                    filtered.push({ emoji: reaction, from });
                                }
                                return { ...m, reactions: filtered };
                            }
                            return m;
                        }));
                    }
                    return;
                }

                // 👤 Processar atualização de perfil
                if (data.type === 'profile_updated') {
                    const { conversation_id, custom_name, whatsapp_name, avatar_url } = data;

                    // Atualiza lista de conversas
                    setConversations(prev => prev.map(c => {
                        if (c.id === conversation_id) {
                            return {
                                ...c,
                                custom_name: custom_name !== undefined ? custom_name : c.custom_name,
                                whatsapp_name: whatsapp_name || c.whatsapp_name,
                                avatar_url: avatar_url || c.avatar_url
                            };
                        }
                        return c;
                    }));

                    console.log(`👤 Perfil atualizado: ${conversation_id}`);
                    return;
                }

                if (data.type === 'new_message') {
                    const { conversation_id, message } = data;
                    // Atualiza mensagem se for a ativa
                    if (activeConversationIdRef.current === conversation_id) {
                        setMessages(prev => {
                            // Verifica duplicação por ID exato
                            if (prev.some(m => m.message_id === message.message_id)) return prev;

                            // Verifica duplicação por conteúdo + sender + timestamp próximo
                            // (previne duplicação de mensagens otimistas enviadas por nós)
                            const isDuplicate = prev.some(m =>
                                m.content === message.content &&
                                m.sender === message.sender &&
                                Math.abs(m.timestamp - message.timestamp) < 5 // 5 segundos de tolerância
                            );

                            let newMessages;
                            if (isDuplicate) {
                                // Remove mensagens temporárias e mantém apenas a real
                                newMessages = prev.filter(m =>
                                    !(m.content === message.content &&
                                        m.sender === message.sender &&
                                        m.message_id.startsWith('temp-'))
                                ).concat([message]);
                            } else {
                                newMessages = [...prev, message];
                            }

                            // 🚀 Atualiza cache também
                            messagesCache.current.set(conversation_id, newMessages);
                            saveCacheToStorage();
                            return newMessages;
                        });
                    }
                    // Atualiza lista
                    setConversations(prev => {
                        const idx = prev.findIndex(c => c.id === conversation_id);

                        // Se não achar, busca tudo (fallback)
                        if (idx === -1) { fetchConversations(); return prev; }

                        const updated = [...prev];
                        const existing = updated[idx];

                        const conv = {
                            ...existing,
                            lastMessage: message.content,
                            lastUpdated: message.timestamp * 1000,
                            // Atualiza dados do perfil se vierem no payload
                            name: data.name || existing.name,
                            avatar_url: data.avatar_url || existing.avatar_url,
                            unreadCount: data.unreadCount !== undefined ? data.unreadCount : (existing.unreadCount || 0)
                        };

                        if (message.sender === 'cliente' && activeConversationIdRef.current !== conversation_id) {
                            conv.unread = true;
                            // Se o backend já mandou a contagem, usa ela. Senão incrementa.
                            if (data.unreadCount === undefined) {
                                conv.unreadCount = (conv.unreadCount || 0) + 1;
                            }
                        }

                        updated[idx] = conv;
                        updated.sort((a, b) => b.lastUpdated - a.lastUpdated);
                        return updated;
                    });
                }
            } catch (e) { }
        };
        ws.onclose = () => { wsRef.current = null; };
        return () => { if (wsRef.current) wsRef.current.close(); };
    }, [token, WS_URL, fetchConversations]);

    // --- 3. AÇÕES ---
    const selectChat = (chat) => { setActiveConversationId(chat.id); };
    const deselectChat = () => { setActiveConversationId(null); };

    const handleSendMessage = async (text) => {
        if (!activeConversationId) return;
        // Otimista
        const tempId = `temp-${Date.now()}`;
        setMessages(prev => [...prev, { content: text, sender: 'vendedor', timestamp: Date.now() / 1000, message_id: tempId }]);

        try {
            await fetch(`${API_BASE_URL}/messages/send`, {
                method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ conversation_id: activeConversationId, message_text: text })
            });
            return true;
        } catch (e) { return false; }
    };

    const handleSendReaction = async (messageId, emoji) => {
        if (!activeConversationId) return;
        try {
            await fetch(`${API_BASE_URL}/messages/react`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({
                    conversation_id: activeConversationId,
                    message_id: messageId,
                    emoji: emoji
                })
            });
            return true;
        } catch (e) {
            console.error('Erro ao enviar reação:', e);
            return false;
        }
    };

    // 👤 Atualiza nome customizado do contato
    const handleUpdateCustomName = async (jid, customName) => {
        try {
            const response = await fetch(`${API_BASE_URL}/contacts/${jid}/custom-name`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ custom_name: customName })
            });

            if (response.ok) {
                console.log(`✏️ Nome customizado atualizado para ${jid}`);
                return true;
            }
            return false;
        } catch (e) {
            console.error('Erro ao atualizar nome:', e);
            return false;
        }
    };

    // 🔄 Atualiza perfil do WhatsApp (foto + nome)
    const handleRefreshProfile = async (jid) => {
        try {
            const response = await fetch(`${API_BASE_URL}/contacts/${jid}/refresh-profile`, {
                method: 'GET',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                const data = await response.json();
                console.log(`🔄 Perfil atualizado para ${jid}:`, data);
                return true;
            }
            return false;
        } catch (e) {
            console.error('Erro ao atualizar perfil:', e);
            return false;
        }
    };

    // 🗑️ Deletar conversa
    const handleDeleteConversation = async (conversationId) => {
        try {
            const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                // Remove localmente
                setConversations(prev => prev.filter(c => c.id !== conversationId));
                if (activeConversationId === conversationId) {
                    setActiveConversationId(null);
                    setMessages([]);
                }
                return true;
            }
            return false;
        } catch (e) {
            console.error('Erro ao deletar conversa:', e);
            return false;
        }
    };

    // 🆕 Iniciar Nova Conversa
    const handleStartConversation = async (number, message) => {
        try {
            const response = await fetch(`${API_BASE_URL}/conversations/start_new`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ recipient_number: number, initial_message: message })
            });

            if (response.ok) {
                const data = await response.json();
                // Se retornou sucesso, atualiza a lista de conversas
                fetchConversations();
                // Opcional: Já selecionar a nova conversa se o backend retornar o ID
                if (data.conversation_id) {
                    setActiveConversationId(data.conversation_id);
                }
                return true;
            }
            return false;
        } catch (e) {
            console.error('Erro ao iniciar conversa:', e);
            return false;
        }
    };

    // --- EXPORTS ---
    const value = {
        conversations, activeConversationId, currentChat, messages, setMessages,
        isCopilotOpen, setIsCopilotOpen, handleToggleCopilot: () => setIsCopilotOpen(p => !p), isMobile,
        selectChat, deselectChat, handleSendMessage, handleSendReaction, handleUpdateCustomName, handleRefreshProfile, handleDeleteConversation, handleStartConversation,
        fetchConversations, refreshConversations: fetchConversations,
        // Copilot
        suggestions, isCopilotLoading, lastAnalyzedMessage, queryType,
        handleSuggestionRequest, handleInternalQuery, clearSuggestions
    };

    return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
};

export const useChat = () => useContext(ChatContext);
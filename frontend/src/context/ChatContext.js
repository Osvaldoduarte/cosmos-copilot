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

    // 🎯 Drag-and-Drop state (compartilhado)
    const [isDragging, setIsDragging] = useState(false);
    const [draggedMessage, setDraggedMessage] = useState(null);

    // Listener de resize para isMobile
    useEffect(() => {
        const handleResize = () => setIsMobile(window.innerWidth <= 768);
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    // --- ESTADOS DO COPILOT (IA) ---
    // Sugestões agora são mapeadas por conversation ID
    // --- ESTADOS DO COPILOT (IA) ---
    // Sugestões agora são mapeadas por conversation ID
    const [suggestionsByConversation, setSuggestionsByConversation] = useState({});

    // 🚦 Fila de Carregamento (Loading por conversa)
    const [loadingStates, setLoadingStates] = useState({}); // { [convId]: true/false }

    const [lastAnalyzedMessage, setLastAnalyzedMessage] = useState(null);
    const [queryType, setQueryType] = useState('analysis'); // 'analysis' ou 'internal'

    // Helper para pegar sugestões da conversa ativa
    const suggestions = activeConversationId ? (suggestionsByConversation[activeConversationId] || null) : null;

    // Helper para saber se a conversa ativa está carregando
    const isCopilotLoading = activeConversationId ? (loadingStates[activeConversationId] || false) : false;

    // --- CONFIG ---
    const { token, handleLogout } = useAuth();
    // --- CONFIGURAÇÃO DE AMBIENTE (LIGA/DESLIGA) ---
    // 💡 COMENTE a linha 'IS_DEV = true' para ir para PRODUÇÃO
    const IS_DEV = true; // (true = dev false = prod)

    const DEV_URL = 'http://localhost:8000';
    const PROD_URL = 'https://cosmos-backend-ocgvnigdzq-uc.a.run.app'; // URL da sua Cloud Run

    const API_BASE_URL = IS_DEV ? DEV_URL : PROD_URL;
    const WS_URL = API_BASE_URL.replace(/^http/, 'ws') + '/ws';

    // Derivados
    const currentChat = conversations.find(c => c.id === activeConversationId) || null;
    const activeConversationIdRef = useRef(activeConversationId);
    const wsRef = useRef(null);

    useEffect(() => { activeConversationIdRef.current = activeConversationId; }, [activeConversationId]);

    // --- 1. FUNÇÕES DO COPILOT ---

    const clearSuggestions = useCallback(() => {
        if (activeConversationId) {
            setSuggestionsByConversation(prev => {
                const updated = { ...prev };
                delete updated[activeConversationId];
                return updated;
            });
        }
        setLastAnalyzedMessage(null);
        setQueryType('analysis');
    }, [activeConversationId]);

    // Ação: Analisar mensagem do cliente (Botão direito ou Automático)
    const handleSuggestionRequest = async (text, conversationId) => {
        if (!text) return;

        // Marca esta conversa como carregando
        setLoadingStates(prev => ({ ...prev, [conversationId]: true }));

        setQueryType('analysis');
        setLastAnalyzedMessage(text);

        if (!isCopilotOpen) setIsCopilotOpen(true);

        try {
            // Rota do backend que criamos no main.py
            const response = await fetch(`${API_BASE_URL}/ai/generate_suggestion`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ conversation_id: conversationId, query: text, type: 'analysis' })
            });
            const data = await response.json();
            if (data.status === 'success') {
                setSuggestionsByConversation(prev => ({
                    ...prev,
                    [conversationId]: data.suggestions
                }));
            }
        } catch (e) { console.error(e); }
        finally {
            setLoadingStates(prev => {
                const newState = { ...prev };
                delete newState[conversationId];
                return newState;
            });
        }
    };

    // Ação: Pergunta interna (Input do Copilot)
    const handleInternalQuery = async (query) => {
        if (!query || !activeConversationId) return;

        const currentId = activeConversationId; // Captura ID atual
        setLoadingStates(prev => ({ ...prev, [currentId]: true }));

        setQueryType('internal');

        try {
            const response = await fetch(`${API_BASE_URL}/ai/generate_suggestion`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ conversation_id: currentId, query: query, type: 'internal' })
            });
            const data = await response.json();
            if (data.status === 'success') {
                setSuggestionsByConversation(prev => ({
                    ...prev,
                    [currentId]: data.suggestions
                }));
            }
        } catch (e) { console.error(e); }
        finally {
            setLoadingStates(prev => {
                const newState = { ...prev };
                delete newState[currentId];
                return newState;
            });
        }
    };

    // --- ANÁLISE DE CONTEXTO DE VENDAS (Novo) ---
    const [salesContext, setSalesContext] = useState(null);
    const [isAnalyzing, setIsAnalyzing] = useState(false);

    const analyzeSalesContext = useCallback(async (conversationId) => {
        if (!conversationId || !token) return;
        setIsAnalyzing(true);
        setSalesContext(null); // Limpa anterior

        try {
            const response = await fetch(`${API_BASE_URL}/ai/analyze_context`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ conversation_id: conversationId })
            });
            const data = await response.json();
            if (data.status === 'success') {
                setSalesContext(data.analysis);
            }
        } catch (e) { console.error("Erro ao analisar contexto:", e); }
        finally { setIsAnalyzing(false); }
    }, [token, API_BASE_URL]);

    // --- 2. LÓGICA DE CHAT (WebSocket, Fetch, Send) ---
    // (Código mantido da versão anterior que já estava funcionando)

    const fetchConversations = useCallback(async () => {
        if (!token) return;
        try {
            const response = await fetch(`${API_BASE_URL}/conversations`, { headers: { 'Authorization': `Bearer ${token}` } });
            if (response.status === 401) { handleLogout(); return; }
            if (response.ok) {
                const data = await response.json();
                let serverConvs = data.conversations || [];

                // 🚀 Fallback: Se backend vier vazio, tenta reconstruir do cache local
                if (serverConvs.length === 0 && messagesCache.current.size > 0) {
                    console.log("⚠️ Backend vazio. Usando cache local para listar conversas.");
                    const cachedConvs = Array.from(messagesCache.current.keys()).map(jid => {
                        const msgs = messagesCache.current.get(jid);
                        const lastMsg = msgs.length > 0 ? msgs[msgs.length - 1] : null;
                        return {
                            id: jid,
                            name: jid.split('@')[0], // Nome provisório
                            avatar_url: '',
                            lastMessage: lastMsg?.content || '',
                            lastUpdated: lastMsg?.timestamp || Date.now(),
                            unreadCount: 0
                        };
                    });
                    // Ordena por mais recente
                    serverConvs = cachedConvs.sort((a, b) => b.lastUpdated - a.lastUpdated);
                }
                setConversations(serverConvs);
            }
        } catch (error) { console.error("Erro conversas:", error); }
    }, [token, API_BASE_URL, handleLogout]);

    // Load conversations once on mount
    // Real-time updates come via WebSocket 'new_message' event
    useEffect(() => {
        fetchConversations();
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
            // Cache hit: Evita requisição desnecessária se já temos dados
            return;
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

    // WebSocket Connection with Reconnection Logic
    useEffect(() => {
        if (!token) return;

        let connectTimeout;

        const connect = () => {
            // Evita múltiplas conexões
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                return;
            }
            // Limpa conexão anterior se estiver em estado de conexão ou fechamento
            if (wsRef.current) {
                wsRef.current.close();
            }

            const ws = new WebSocket(WS_URL);
            wsRef.current = ws;

            ws.onopen = () => {
                console.log('🟢 WS Conectado');
            };

            ws.onclose = (event) => {
                console.log('⚪️ WS Desconectado:', event.code, event.reason);
                wsRef.current = null;
                // Tenta reconectar após um delay, exceto se o fechamento foi limpo (ex: logout)
                if (event.code !== 1000) {
                    clearTimeout(connectTimeout);
                    connectTimeout = setTimeout(() => {
                        console.log('🔁 Tentando reconectar WS...');
                        connect();
                    }, 5000); // Tenta reconectar a cada 5 segundos
                }
            };

            ws.onerror = (error) => {
                console.error('🔴 WS Erro:', error);
                // Apenas fecha o socket. O 'onclose' handler cuidará da reconexão.
                ws.close();
            };

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
                                    const filtered = reactions.filter(r => r.from !== from);
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

                    // 📖 Processar leitura de conversa
                    if (data.type === 'conversation_read') {
                        const { conversation_id } = data;
                        setConversations(prev => prev.map(c => {
                            if (c.id === conversation_id) {
                                return { ...c, unreadCount: 0, unread: false };
                            }
                            return c;
                        }));
                        return;
                    }

                    if (data.type === 'new_message') {
                        const { conversation_id, message } = data;

                        // 1. Se for a conversa ativa, busca mensagens atualizadas do backend
                        if (activeConversationIdRef.current === conversation_id) {
                            console.log(`🔄 WS: Nova mensagem em ${conversation_id}, atualizando...`);
                            fetchMessages(conversation_id);
                        }

                        // 2. Atualiza a lista de conversas (para ordenar e mostrar unread)
                        fetchConversations();

                        // (Opcional) Mantemos a atualização otimista local se quiser, 
                        // mas o fetch garante a verdade absoluta (incluindo transcrições que o backend fizer)
                    }
                } catch (e) {
                    console.error("🔴 Erro ao processar mensagem WS:", e);
                }
            };
        };

        connect();

        return () => {
            clearTimeout(connectTimeout);
            if (wsRef.current) {
                // Remove o handler de reconexão para evitar que tente reconectar num unmount limpo
                wsRef.current.onclose = () => {
                    console.log('⚪️ WS Desconectado de forma limpa.');
                };
                wsRef.current.close(1000, "Component unmounting");
            }
        };
    }, [token, WS_URL, fetchConversations]);

    // --- 3. AÇÕES ---
    const selectChat = async (chat) => {
        setActiveConversationId(chat.id);

        // Otimista: Marca como lido localmente imediatamente
        setConversations(prev => prev.map(c => {
            if (c.id === chat.id) {
                return { ...c, unreadCount: 0, unread: false };
            }
            return c;
        }));

        // Marcar como lido no backend (Apenas se tiver não lidas)
        if (chat.unreadCount > 0 || chat.unread) {
            try {
                await fetch(`${API_BASE_URL}/conversations/${encodeURIComponent(chat.id)}/mark_read`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    }
                });
            } catch (error) {
                console.error('Erro ao marcar como lido:', error);
            }
        }
    };
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

                // 🚀 ATUALIZA A LISTA DE CONVERSAS TAMBÉM
                setConversations(prev => prev.map(c => {
                    if (c.id === jid) {
                        return {
                            ...c,
                            name: data.pushName || data.name || c.name,
                            avatar_url: data.picture || c.avatar_url
                        };
                    }
                    return c;
                }));

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

    // 🚀 Carrega conversas iniciais (últimas 20 conversas, 40 mensagens cada)
    const [isLoadingInitial, setIsLoadingInitial] = useState(false);

    const loadInitialConversations = async () => {
        if (!token) return false;
        setIsLoadingInitial(true);

        try {
            console.log("🚀 Carregando conversas iniciais...");
            const response = await fetch(`${API_BASE_URL}/sync/initial_load`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                const data = await response.json();
                console.log(`✅ ${data.loaded} conversas carregadas de ${data.total_available} disponíveis`);

                // Atualiza lista de conversas
                await fetchConversations();
                return true;
            }
            return false;
        } catch (e) {
            console.error('Erro ao carregar conversas:', e);
            return false;
        } finally {
            setIsLoadingInitial(false);
        }
    };

    // --- EXPORTS ---
    const value = {
        conversations, activeConversationId, currentChat, messages, setMessages,
        isCopilotOpen, setIsCopilotOpen, handleToggleCopilot: () => setIsCopilotOpen(p => !p), isMobile,
        selectChat, deselectChat, handleSendMessage, handleSendReaction, handleUpdateCustomName, handleRefreshProfile, handleDeleteConversation, handleStartConversation,
        fetchConversations, refreshConversations: fetchConversations,
        // Initial Load
        loadInitialConversations, isLoadingInitial,
        // Copilot
        suggestions, isCopilotLoading, lastAnalyzedMessage, queryType,
        handleSuggestionRequest, handleInternalQuery, clearSuggestions,
        // Sales Context
        salesContext, isAnalyzing, analyzeSalesContext,
        // Drag-and-Drop
        isDragging, setIsDragging, draggedMessage, setDraggedMessage
    };

    return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
};

export const useChat = () => useContext(ChatContext);
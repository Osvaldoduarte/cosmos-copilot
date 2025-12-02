import React, { useState, useEffect } from 'react';
import { useChat, getDisplayName } from '../context/ChatContext';
import { useAuth } from '../hooks/useAuth';
import '../styles/layout.css';
import ChatPanel from './ChatPanel';
import CopilotPanel from './CopilotPanel';
import DragDropZone from './DragDropZone';

// Componentes
import NewConversationModal from './NewConversationModal';

// Ícones
const CloudDownloadIcon = () => (<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>);
const SearchIcon = () => (<svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>);
const PlusIcon = () => (<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>);

const Toast = ({ message, type, onClose }) => {
    React.useEffect(() => {
        const timer = setTimeout(onClose, 4000);
        return () => clearTimeout(timer);
    }, [onClose]);

    return (
        <div className={`custom-toast ${type}`}>
            {type === 'success' ? '✔' : '✖'} <span>{message}</span>
        </div>
    );
};

// --- FUNÇÕES AUXILIARES DE BUSCA (FUZZY) ---
const levenshteinDistance = (a, b) => {
    if (a.length === 0) return b.length;
    if (b.length === 0) return a.length;

    const matrix = [];
    for (let i = 0; i <= b.length; i++) { matrix[i] = [i]; }
    for (let j = 0; j <= a.length; j++) { matrix[0][j] = j; }

    for (let i = 1; i <= b.length; i++) {
        for (let j = 1; j <= a.length; j++) {
            if (b.charAt(i - 1) === a.charAt(j - 1)) {
                matrix[i][j] = matrix[i - 1][j - 1];
            } else {
                matrix[i][j] = Math.min(
                    matrix[i - 1][j - 1] + 1,
                    matrix[i][j - 1] + 1,
                    matrix[i - 1][j] + 1
                );
            }
        }
    }
    return matrix[b.length][a.length];
};

const fuzzyMatch = (text, search) => {
    if (!text) return false;
    const cleanText = text.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    const cleanSearch = search.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");

    // 1. Match exato (substring)
    if (cleanText.includes(cleanSearch)) return true;

    // 2. Match aproximado (Levenshtein) para buscas > 3 chars
    if (cleanSearch.length > 3) {
        const words = cleanText.split(/\s+/);
        // Verifica se alguma palavra do texto é similar à busca
        for (const word of words) {
            if (levenshteinDistance(word, cleanSearch) <= 2) return true;
        }
    }
    return false;
};

const MainLayout = ({ onLogout }) => {
    // --- ESTADOS E HOOKS ---
    const [notification, setNotification] = useState(null);
    const notify = (msg, type = 'success') => setNotification({ message: msg, type });
    const { conversations, currentChat, selectChat, deselectChat, refreshConversations, isCopilotOpen, handleDeleteConversation, loadInitialConversations, isLoadingInitial } = useChat();
    const { token } = useAuth();

    // Controle de Modais
    const [isNewChatModalOpen, setIsNewChatModalOpen] = useState(false);
    const [showImportModal, setShowImportModal] = useState(false);
    const [openMenuId, setOpenMenuId] = useState(null);

    const handleMenuClick = (e, chatId) => {
        e.stopPropagation();
        setOpenMenuId(openMenuId === chatId ? null : chatId);
    };

    const handleDeleteChat = async (e, chatId, chatName) => {
        e.stopPropagation();
        if (window.confirm(`Tem certeza que deseja apagar a conversa com ${chatName}?`)) {
            const success = await handleDeleteConversation(chatId);
            if (success) {
                setOpenMenuId(null);
                notify("Conversa apagada", "success");
            } else {
                notify("Erro ao apagar conversa", "error");
            }
        }
    };

    // Controle de Importação
    const [availableChats, setAvailableChats] = useState([]);
    const [selectedJids, setSelectedJids] = useState(new Set());
    const [isLoadingChats, setIsLoadingChats] = useState(false);
    const [isImporting, setIsImporting] = useState(false);

    // Controle de Pesquisa
    const [searchTerm, setSearchTerm] = useState('');
    const [importSearchTerm, setImportSearchTerm] = useState('');

    const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

    const [currentPage, setCurrentPage] = useState(1);
    const [hasMoreChats, setHasMoreChats] = useState(false);

    // --- LÓGICA DE PESQUISA (COM FUZZY E MENSAGENS) ---
    const filteredConversations = conversations.filter(chat =>
        fuzzyMatch(getDisplayName(chat), searchTerm) || fuzzyMatch(chat.lastMessage, searchTerm)
    );

    // Filtra chats disponíveis para importação - REMOVIDO, agora é no backend
    // const filteredImportChats = availableChats.filter...

    const loadChats = async (page = 1, searchQuery = '') => {
        setIsLoadingChats(true);
        try {
            // Passa a página E o termo de busca na URL
            const params = new URLSearchParams({
                page: page.toString(),
                limit: '10'
            });

            if (searchQuery && searchQuery.trim()) {
                params.append('search', searchQuery.trim());
            }

            const res = await fetch(`${API_URL}/evolution/chats/summary?${params}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (res.ok) {
                const responseData = await res.json();

                // Se for página 1, substitui. Se for > 1, adiciona ao final.
                if (page === 1) {
                    setAvailableChats(responseData.data);
                } else {
                    setAvailableChats(prev => [...prev, ...responseData.data]);
                }

                setHasMoreChats(responseData.has_more);
                setCurrentPage(page);
            }
        } catch (error) {
            console.error("Erro chats:", error);
        } finally {
            setIsLoadingChats(false);
        }
    };

    // --- FUNÇÕES DE IMPORTAÇÃO ---
    const handleOpenImport = () => {
        setShowImportModal(true);
        setAvailableChats([]); // Limpa lista anterior
        setImportSearchTerm(''); // Limpa busca
        loadChats(1); // Carrega primeira página
    };

    // Debounce para busca (busca no backend após 500ms de pausa na digitação)
    useEffect(() => {
        if (!showImportModal) return;

        const timer = setTimeout(() => {
            loadChats(1, importSearchTerm); // Sempre volta para página 1 ao buscar
        }, 500);

        return () => clearTimeout(timer);
    }, [importSearchTerm, showImportModal]);

    const toggleChatSelection = (jid) => {
        const newSet = new Set(selectedJids);
        if (newSet.has(jid)) newSet.delete(jid); else newSet.add(jid);
        setSelectedJids(newSet);
    };

    const handleSelectAll = () => {
        if (selectedJids.size === availableChats.length) setSelectedJids(new Set());
        else setSelectedJids(new Set(availableChats.map(c => c.id)));
    };

    const executeImport = async () => {
        if (selectedJids.size === 0) return;
        setIsImporting(true);
        try {
            const res = await fetch(`${API_URL}/evolution/chats/import`, {
                method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ jids: Array.from(selectedJids) })
            });
            if (res.ok) {
                setShowImportModal(false);
                setSelectedJids(new Set());

                // SUBSTITUÍDO: alert(...) POR notify(...)
                notify("Importação iniciada! Atualizando lista...", "success");

                // Refresh escalonado
                setTimeout(() => { if (refreshConversations) refreshConversations(); }, 2000);
                setTimeout(() => { if (refreshConversations) refreshConversations(); }, 5000);
            }
        } catch (error) { notify("Erro ao solicitar importação.", "error"); } finally { setIsImporting(false); }
    };

    return (
        <div className="main-layout">
            {/* 4. RENDERIZE O TOAST NO TOPO DO LAYOUT */}
            {notification && <Toast message={notification.message} type={notification.type} onClose={() => setNotification(null)} />}
            {/* --- SIDEBAR --- */}
            <aside className={`sidebar ${currentChat ? 'hide-on-mobile' : ''}`}>

                {/* HEADER DA SIDEBAR */}
                <div className="sidebar-header">
                    <h2>Conversas</h2>
                    <div style={{ display: 'flex', gap: '8px' }}>
                        {/* Botão Importar */}
                        <button onClick={handleOpenImport} className="btn-icon-small" title="Importar do WhatsApp">
                            <CloudDownloadIcon />
                        </button>

                        {/* Botão Nova Conversa (Agora funciona!) */}
                        <button onClick={() => setIsNewChatModalOpen(true)} className="btn-icon-small" title="Nova Conversa">
                            <PlusIcon />
                        </button>
                    </div>
                </div>

                {/* BARRA DE PESQUISA (RESTAURADA) */}
                <div className="sidebar-search-bar">
                    <div className="sidebar-search-wrapper">
                        <div className="sidebar-search-icon">
                            <SearchIcon />
                        </div>
                        <input
                            className="sidebar-search-input"
                            type="text"
                            placeholder="Buscar conversa..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                        />
                    </div>
                </div>

                {/* LISTA DE CONVERSAS */}
                <div className="conversations-list custom-scroll">
                    {filteredConversations.length === 0 ? (
                        <div style={{
                            textAlign: 'center',
                            padding: '40px 20px',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '16px',
                            alignItems: 'center'
                        }}>
                            <div style={{ color: '#64748b', fontSize: '0.9rem' }}>
                                {searchTerm ? 'Nenhuma conversa encontrada.' : 'Nenhuma conversa carregada.'}
                            </div>
                            {!searchTerm && (
                                <button
                                    onClick={loadInitialConversations}
                                    disabled={isLoadingInitial}
                                    style={{
                                        padding: '12px 24px',
                                        background: 'linear-gradient(135deg, #3b82f6 0%, #1e40af 100%)',
                                        border: 'none',
                                        borderRadius: '12px',
                                        color: 'white',
                                        fontSize: '0.9rem',
                                        fontWeight: '500',
                                        cursor: isLoadingInitial ? 'wait' : 'pointer',
                                        opacity: isLoadingInitial ? 0.7 : 1,
                                        transition: 'all 0.2s',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '8px',
                                        boxShadow: '0 4px 12px rgba(59, 130, 246, 0.3)'
                                    }}
                                    onMouseEnter={(e) => {
                                        if (!isLoadingInitial) {
                                            e.target.style.transform = 'translateY(-2px)';
                                            e.target.style.boxShadow = '0 6px 16px rgba(59, 130, 246, 0.4)';
                                        }
                                    }}
                                    onMouseLeave={(e) => {
                                        e.target.style.transform = 'translateY(0)';
                                        e.target.style.boxShadow = '0 4px 12px rgba(59, 130, 246, 0.3)';
                                    }}
                                >
                                    {isLoadingInitial ? (
                                        <>
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" style={{ animation: 'spin 1s linear infinite' }}>
                                                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" opacity="0.25" />
                                                <path d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" fill="currentColor" />
                                            </svg>
                                            Carregando...
                                        </>
                                    ) : (
                                        <>
                                            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                                                <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z" />
                                            </svg>
                                            Carregar Conversas
                                        </>
                                    )}
                                </button>
                            )}
                        </div>
                    ) : (
                        filteredConversations.map(chat => (
                            <div key={chat.id} onClick={() => selectChat(chat)} className={`conversation-item ${currentChat?.id === chat.id ? 'active' : ''}`}>
                                {chat.avatar_url ? (
                                    <img src={chat.avatar_url} alt="" className="avatar-placeholder" style={{ objectFit: 'cover' }} />
                                ) : (
                                    <div className="avatar-placeholder">{getDisplayName(chat).charAt(0)}</div>
                                )}
                                <div className="conv-info">
                                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                        <h4>{getDisplayName(chat)}</h4>
                                        {chat.lastUpdated && <span style={{ fontSize: '0.7rem', color: '#64748b' }}>{new Date(chat.lastUpdated).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>}
                                    </div>
                                    <p>{chat.lastMessage || "..."}</p>
                                </div>

                                {/* ACTIONS MENU */}
                                <div className={`conversation-actions-wrapper ${openMenuId === chat.id ? 'active' : ''}`}>
                                    <button className="action-dots-btn" onClick={(e) => handleMenuClick(e, chat.id)}>
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z" /></svg>
                                    </button>
                                    {openMenuId === chat.id && (
                                        <div className="action-dropdown-menu">
                                            <button onClick={(e) => handleDeleteChat(e, chat.id, getDisplayName(chat))} className="danger-action">
                                                Apagar Conversa
                                            </button>
                                        </div>
                                    )}
                                </div>

                                {chat.unreadCount > 0 && <div className="unread-badge-sidebar">{chat.unreadCount}</div>}
                            </div>
                        ))
                    )}
                </div>

                {/* FOOTER */}
                <div className="sidebar-footer">
                    <button onClick={() => window.location.href = '/manager'} className="btn-footer-secondary">Gerencial</button>
                    <button onClick={onLogout} className="btn-footer-danger">Sair</button>
                </div>
            </aside>

            {/* --- CHAT AREA --- */}
            <main className="chat-area">
                {!currentChat ? (
                    <div className="empty-state">
                        <p>Selecione uma conversa ou use o botão <CloudDownloadIcon /> para importar.</p>
                    </div>
                ) : (
                    // Aqui você deve renderizar seu componente de Chat real (ChatPanel)
                    // Exemplo placeholder, substitua pelo seu <ChatPanel />
                    <ChatPanel onBack={deselectChat} />
                )}
            </main>

            {/* --- COPILOT PANEL (DIREITA) --- */}
            {isCopilotOpen && (
                <aside className="copilot-sidebar">
                    <CopilotPanel />
                </aside>
            )}

            {/* --- MODAL IMPORTAR --- */}
            {showImportModal && (
                <div className="modal-backdrop">
                    <div className="modal-panel glass-effect" style={{ maxWidth: '500px', maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
                        <div className="modal-header">
                            <h3>Importar do WhatsApp</h3>
                            <button onClick={() => setShowImportModal(false)} style={{ background: 'none', border: 'none', color: 'white', fontSize: '1.5rem', cursor: 'pointer' }}>×</button>
                        </div>
                        <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '1rem' }}>Selecione as conversas para importar (50 msgs).</p>

                        {/* Campo de Busca */}
                        <div className="sidebar-search-bar" style={{ padding: '0 0 1rem 0', borderBottom: 'none' }}>
                            <div className="sidebar-search-wrapper">
                                <div className="sidebar-search-icon">
                                    <SearchIcon />
                                </div>
                                <input
                                    className="sidebar-search-input"
                                    type="text"
                                    placeholder="Buscar por nome ou número..."
                                    value={importSearchTerm}
                                    onChange={(e) => setImportSearchTerm(e.target.value)}
                                />
                            </div>
                        </div>

                        {isLoadingChats ? (
                            <div style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '200px' }}><div className="spinner-dot"></div></div>
                        ) : (
                            <>
                                <div className="import-actions-bar" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                                    <button onClick={handleSelectAll} className="text-btn">{selectedJids.size === availableChats.length ? "Desmarcar" : "Todos"}</button>
                                    <span style={{ fontSize: '0.85rem', color: '#cbd5e1' }}>{selectedJids.size} selecionados</span>
                                </div>
                                <div className="chats-import-list custom-scroll" style={{ flex: 1, overflowY: 'auto', border: '1px solid #334155', borderRadius: '8px', marginBottom: '10px' }}>
                                    {availableChats.length === 0 ? (
                                        <div style={{ textAlign: 'center', padding: '40px 20px', color: '#64748b' }}>
                                            {importSearchTerm ? 'Nenhuma conversa encontrada.' : 'Nenhuma conversa disponível.'}
                                        </div>
                                    ) : (
                                        availableChats.map(chat => (
                                            <div key={chat.id} onClick={() => toggleChatSelection(chat.id)} className={`import-item ${selectedJids.has(chat.id) ? 'selected' : ''}`}>
                                                <div className="checkbox-custom">{selectedJids.has(chat.id) && <span>✔</span>}</div>
                                                {chat.picture ? <img src={chat.picture} alt="" className="import-avatar" /> : <div className="import-avatar-placeholder">{chat.name?.charAt(0)}</div>}
                                                <div className="import-info"><h4>{chat.name}</h4><span className="import-subtitle">{chat.id.split('@')[0]}</span></div>
                                            </div>
                                        ))
                                    )}
                                </div>
                                {!isLoadingChats && hasMoreChats && (
                                    <button
                                        onClick={() => loadChats(currentPage + 1)}
                                        className="text-btn full-width"
                                        style={{ padding: '15px', borderTop: '1px solid #334155', color: '#60a5fa' }}
                                    >
                                        Carregar mais conversas...
                                    </button>
                                )}
                                <button onClick={executeImport} disabled={selectedJids.size === 0 || isImporting} className="btn-primary-glow full-width" style={{ marginTop: '1.5rem', justifyContent: 'center' }}>
                                    {isImporting ? 'Importando...' : 'Importar Conversas'}
                                </button>
                            </>
                        )}
                    </div>
                </div>
            )}

            {/* --- MODAL NOVA CONVERSA --- */}
            {isNewChatModalOpen && (
                <NewConversationModal
                    isOpen={isNewChatModalOpen}
                    onClose={() => setIsNewChatModalOpen(false)}
                    onConversationStart={refreshConversations} // Atualiza lista ao criar
                />
            )}

            {/* 🎯 Drop Zone para quando Copilot está fechado */}
            <DragDropZone />

        </div>
    );
};

export default MainLayout;
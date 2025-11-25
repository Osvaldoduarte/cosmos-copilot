import React, { useState, useEffect } from 'react';
import { useChat } from '../context/ChatContext';
import { useAuth } from '../hooks/useAuth';
import '../styles/layout.css';
import ChatPanel from './ChatPanel';
import CopilotPanel from './CopilotPanel';

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

const MainLayout = ({ onLogout }) => {
    // --- ESTADOS E HOOKS ---
    const [notification, setNotification] = useState(null);
    const notify = (msg, type = 'success') => setNotification({ message: msg, type });
    const { conversations, currentChat, selectChat, deselectChat, refreshConversations, isCopilotOpen } = useChat();
    const { token } = useAuth();

    // Controle de Modais
    const [isNewChatModalOpen, setIsNewChatModalOpen] = useState(false);
    const [showImportModal, setShowImportModal] = useState(false);

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

    // --- LÓGICA DE PESQUISA ---
    const filteredConversations = conversations.filter(chat =>
        chat.name?.toLowerCase().includes(searchTerm.toLowerCase())
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
                        <div style={{ textAlign: 'center', padding: '20px', color: '#64748b', fontSize: '0.9rem' }}>
                            {searchTerm ? 'Nenhuma conversa encontrada.' : 'Nenhuma conversa iniciada.'}
                        </div>
                    ) : (
                        filteredConversations.map(chat => (
                            <div key={chat.id} onClick={() => selectChat(chat)} className={`conversation-item ${currentChat?.id === chat.id ? 'active' : ''}`}>
                                <div className="avatar-placeholder">{chat.name?.charAt(0)}</div>
                                <div className="conv-info">
                                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                        <h4>{chat.name}</h4>
                                        {chat.lastUpdated && <span style={{ fontSize: '0.7rem', color: '#64748b' }}>{new Date(chat.lastUpdated).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>}
                                    </div>
                                    <p>{chat.lastMessage || "..."}</p>
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

        </div>
    );
};

export default MainLayout;
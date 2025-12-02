import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useNavigate } from 'react-router-dom';
import { useToast } from '../context/ToastContext';
// Se estiver usando imagem direta (base64), não precisa do QRCodeSVG,
// mas se quiser manter a biblioteca instalada, não tem problema.
import '../styles/management.css';

// --- ÍCONES ---
const Icons = {
    User: () => <svg className="icon" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>,
    Plus: () => <svg className="icon" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>,
    Chart: () => <svg className="icon" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>,
    Clock: () => <svg className="icon" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
    Brain: () => <svg className="icon" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>,
    X: () => <svg className="icon" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>,
    Cog: () => <svg className="icon" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>,
    Whatsapp: () => <svg className="icon-large" fill="currentColor" viewBox="0 0 24 24"><path d="M.057 24l1.687-6.163c-1.041-1.804-1.588-3.849-1.587-5.946.003-6.556 5.338-11.891 11.893-11.891 3.181.001 6.167 1.24 8.413 3.488 2.245 2.248 3.481 5.236 3.48 8.414-.003 6.557-5.338 11.892-11.893 11.892-1.99-.001-3.951-.5-5.688-1.448l-6.305 1.654zm6.597-3.807c1.676.995 3.276 1.591 5.392 1.592 5.448 0 9.886-4.434 9.889-9.885.002-5.462-4.415-9.89-9.881-9.892-5.452 0-9.887 4.434-9.889 9.884-.001 2.225.651 3.891 1.746 5.634l-.999 3.648 3.742-.981zm11.387-5.464c-.074-.124-.272-.198-.57-.347-.297-.149-1.758-.868-2.031-.967-.272-.099-.47-.149-.669.149-.198.297-.768.967-.941 1.165-.173.198-.347.223-.644.074-.297-.149-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.297-.347.446-.52.151-.174.2-.297.3-.495.099-.198.05-.372-.025-.52-.074-.149-.669-1.611-.916-2.207-.242-.579-.487-.501-.669-.51l-.57-.01c-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.463 1.065 2.875 1.213 3.074.149.198 2.095 3.2 5.076 4.487.709.306 1.263.489 1.694.626.712.226 1.36.194 1.872.118.571-.085 1.758-.719 2.006-1.413.248-.695.248-1.29.173-1.414z" /></svg>,
    MsgText: () => <svg className="icon-sm" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" /></svg>,
    MsgAudio: () => <svg className="icon-sm" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" /></svg>,
    MsgImage: () => <svg className="icon-sm" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>,
    Pencil: () => <svg className="icon-xs" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>,
    Trash: () => <svg className="icon-xs" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>,
    Scan: () => <svg className="icon" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" /></svg>
};

const ManagementPage = () => {
    const { token, handleLogout, handleConnectSuccess } = useAuth();
    const navigate = useNavigate();
    const notify = useToast();

    const [dashboardData, setDashboardData] = useState(null);
    const [loading, setLoading] = useState(true);

    // Modais e Estado
    const [showUserModal, setShowUserModal] = useState(false);
    const [showSettingsModal, setShowSettingsModal] = useState(false);
    const [selectedUser, setSelectedUser] = useState(null);

    // QR Code
    const [qrCode, setQrCode] = useState(null);
    const [isGeneratingQr, setIsGeneratingQr] = useState(false);

    // Formulários
    const [userForm, setUserForm] = useState({ username: '', password: '', full_name: '' });
    const [isEditing, setIsEditing] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [companySettings, setCompanySettings] = useState({ name: '', phone: '' }); // Adicionado

    const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

    // Variável isOnline definida aqui
    const isOnline = dashboardData?.connection_status === 'open';

    // Mocks
    const generateMockMetrics = (userId) => ({
        response: (Math.random() * 5 + 1).toFixed(1) + ' min',
        clients_week: Math.floor(Math.random() * 20) + 5,
        clients_month: Math.floor(Math.random() * 80) + 20,
        ai_usage: (Math.random() * 10).toFixed(1) + 'k',
        messages: { total: 320, text: 200, audio: 50, image: 40, video: 30 },
        pie: { text: 60, audio: 15, image: 15, video: 10 }
    });

    const fetchDashboard = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/manager/dashboard`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) throw new Error("API Error");

            const data = await response.json();

            if (!data.globalMetrics) {
                data.users = data.users.map(u => ({ ...u, metrics: generateMockMetrics(u.username) }));
                data.globalMetrics = { active_clients: 142, avg_response: '3.2 min', total_ai: '124k', total_team: data.users.length };
            }

            setDashboardData(data);
            setCompanySettings({ name: data.company_name, phone: '' }); // Popula settings

        } catch (error) {
            console.error("Usando dados de fallback:", error);
            setDashboardData({
                company_name: "Cosmos Visual", instance_name: "cosmos-demo", connection_status: "close",
                globalMetrics: { active_clients: 0, avg_response: '-', total_ai: '0', total_team: 0 },
                users: []
            });
        } finally {
            setLoading(false);
        }
    }, [token, API_URL]);

    useEffect(() => {
        fetchDashboard();
        const interval = setInterval(() => {
            if (dashboardData?.connection_status !== 'open') fetchDashboard();
        }, 5000);
        return () => clearInterval(interval);
    }, [fetchDashboard, dashboardData?.connection_status]);

    // --- AUTO-REFRESH DO QR CODE ---
    useEffect(() => {
        let interval;
        // Agora 'isOnline' já foi declarado acima, então pode ser usado aqui
        if (qrCode && !isOnline) {
            interval = setInterval(() => {
                console.log("🔄 Atualizando QR Code...");
                handleGenerateQR();
            }, 15000);
        }
        return () => clearInterval(interval);
    }, [qrCode, isOnline]);

    const handleGenerateQR = async () => {
        setIsGeneratingQr(true);
        try {
            const response = await fetch(`${API_URL}/evolution/instance/create_and_get_qr`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            const data = await response.json();
            console.log("📦 Resposta Backend:", data);

            const qrBase64 = data.qrcode?.base64 || data.base64 || data.code || data.url;

            if (qrBase64) {
                const finalSrc = qrBase64.startsWith('data:') ? qrBase64 : `data:image/png;base64,${qrBase64}`;
                setQrCode(finalSrc);
            } else if (data.instance?.state === 'open') {
                notify.success("WhatsApp Conectado!");
                fetchDashboard();
            }
        } catch (error) {
            console.error("Erro QR:", error);
            notify.error("Erro ao conectar ao WhatsApp");
        } finally {
            setIsGeneratingQr(false);
        }
    };

    const handleBackToChat = () => {
        if (isOnline) {
            handleConnectSuccess(); // Força o aviso novamente
            navigate('/app');
        } else {
            notify.warning("Você precisa conectar o WhatsApp primeiro!");
        }
    };

    // --- CRUD HANDLERS ---
    const openNewUserModal = () => { setUserForm({ username: '', password: '', full_name: '' }); setIsEditing(false); setShowUserModal(true); };
    const openEditUserModal = (user, e) => { e.stopPropagation(); setUserForm({ username: user.username, full_name: user.full_name, password: '' }); setIsEditing(true); setShowUserModal(true); };

    const handleSaveUser = async (e) => {
        e.preventDefault();
        setIsSubmitting(true);
        const endpoint = isEditing ? `${API_URL}/manager/users/${userForm.username}` : `${API_URL}/manager/add_user`;
        const method = isEditing ? 'PUT' : 'POST';
        try {
            const response = await fetch(endpoint, {
                method: method,
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify(userForm)
            });
            if (response.ok) {
                notify.success(isEditing ? "Usuário atualizado com sucesso!" : "Usuário criado com sucesso!");
                setShowUserModal(false);
                fetchDashboard();
            } else {
                const err = await response.json();
                notify.error("Erro: " + err.detail);
            }
        } catch (error) { notify.error("Erro de conexão com o servidor"); } finally { setIsSubmitting(false); }
    };

    const handleDeleteUser = async (username, e) => {
        e.stopPropagation();
        if (!window.confirm(`Remover ${username}?`)) return;
        try {
            const response = await fetch(`${API_URL}/manager/users/${username}`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${token}` } });
            if (response.ok) fetchDashboard();
            else notify.error("Erro ao remover usuário");
        } catch (error) { notify.error("Erro inesperado"); }
    };

    const handleSaveSettings = (e) => {
        e.preventDefault();
        notify.success("Configurações salvas com sucesso!"); // Implementar rota depois
        setShowSettingsModal(false);
    };

    const getInitials = (name) => name ? name.split(' ').map(n => n[0]).join('').toUpperCase().substring(0, 2) : '??';

    if (loading) return (
        <div className="loading-container">
            <div className="spinner"></div>
            {/* Opcional: Texto carregando */}
            <span style={{ fontSize: '0.9rem', opacity: 0.7 }}>Carregando painel...</span>
        </div>
    );

    const formatNumber = (num) => {
        if (!num) return '0';
        const n = parseInt(num);
        if (isNaN(n)) return num;
        if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
        if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
        return n.toString();
    };

    return (
        <div className="dashboard-container">
            <div className="dashboard-content-wrapper">

                <header className="dashboard-header">
                    <div>
                        <h1 className="header-title">Painel Gerencial</h1>
                        <div className="header-info">
                            <span className="company-name">{dashboardData?.company_name}</span>
                            <span className="separator">•</span>
                            <span className="instance-id">ID: {dashboardData?.instance_name?.replace('cosmos-', '')}</span>
                        </div>
                    </div>
                    <div className="header-actions">
                        <button onClick={() => setShowSettingsModal(true)} className="btn btn-icon" title="Configurações"><Icons.Cog /></button>
                        <button className="btn-secondary" onClick={handleBackToChat}>
                            Voltar ao Chat
                        </button>
                        <button onClick={handleLogout} className="btn btn-danger">Sair</button>
                    </div>
                </header>

                {/* KPIs */}
                <div className="kpi-grid">
                    <div className="kpi-card"><div className="kpi-icon blue"><Icons.Chart /></div><div><p className="kpi-label">Clientes</p><p className="kpi-value">{dashboardData?.globalMetrics.active_clients}</p></div></div>
                    <div className="kpi-card"><div className="kpi-icon green"><Icons.Clock /></div><div><p className="kpi-label">Tempo Médio</p><p className="kpi-value">{dashboardData?.globalMetrics.avg_response}</p></div></div>
                    <div className="kpi-card"><div className="kpi-icon purple"><Icons.Brain /></div><div><p className="kpi-label">Uso IA</p><p className="kpi-value">{formatNumber(dashboardData?.globalMetrics.total_ai)}</p></div></div>
                    <div className="kpi-card"><div className="kpi-icon orange"><Icons.User /></div><div><p className="kpi-label">Equipe</p><p className="kpi-value">{dashboardData?.globalMetrics.total_team}</p></div></div>
                </div>

                <div className="main-grid">

                    {/* STATUS WHATSAPP */}
                    <div className={`card status-compact ${isOnline ? 'status-online' : 'status-offline'}`}>
                        <div className="status-header-compact">
                            <div className={`status-dot ${isOnline ? 'pulse' : ''}`}></div>
                            <h3>WhatsApp {isOnline ? 'Online' : 'Offline'}</h3>
                        </div>

                        <div className="qr-area">
                            {isOnline ? (
                                <div className="online-state">
                                    <Icons.Whatsapp />
                                    <span className="status-text">CONECTADO</span>
                                </div>
                            ) : (
                                <div className="offline-state">
                                    {qrCode ? (
                                        <div className="qr-wrapper">
                                            <img src={qrCode} alt="QR Code" style={{ width: '100%', height: 'auto' }} />
                                            <p className="qr-instruction">Escaneie com seu celular</p>
                                        </div>
                                    ) : (
                                        <div className="connect-action">
                                            <button onClick={handleGenerateQR} disabled={isGeneratingQr} className="btn btn-primary">
                                                {isGeneratingQr ? 'Gerando...' : <><Icons.Scan /> Gerar QR Code</>}
                                            </button>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* LISTA DE EQUIPE */}
                    <div className="team-section">
                        <div className="section-header">
                            <h2>Membros da Equipe</h2>
                            <button onClick={openNewUserModal} className="btn btn-primary btn-sm">
                                <Icons.Plus /> Adicionar Vendedor
                            </button>
                        </div>
                        <div className="users-grid-cards">
                            {dashboardData?.users.map((user, idx) => (
                                <div key={idx} className="user-card-simple" onClick={() => setSelectedUser(user)}>
                                    <div className="user-card-avatar">{getInitials(user.full_name)}</div>
                                    <div className="user-card-info"><h4>{user.full_name}</h4><p>@{user.username}</p></div>
                                    <div className="user-actions">
                                        <button onClick={(e) => openEditUserModal(user, e)} className="action-icon edit"><Icons.Pencil /></button>
                                        <button onClick={(e) => handleDeleteUser(user.username, e)} className="action-icon delete"><Icons.Trash /></button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* MODAL USUÁRIO */}
            {showUserModal && (
                <div className="modal-overlay">
                    <div className="modal-content">
                        <div className="modal-header"><h3>{isEditing ? 'Editar' : 'Novo'}</h3><button onClick={() => setShowUserModal(false)} className="close-btn"><Icons.X /></button></div>
                        <form onSubmit={handleSaveUser} className="modal-form">
                            <input required type="text" placeholder="Nome" value={userForm.full_name} onChange={e => setUserForm({ ...userForm, full_name: e.target.value })} />
                            <input required type="text" placeholder="Login" value={userForm.username} disabled={isEditing} onChange={e => setUserForm({ ...userForm, username: e.target.value })} className={isEditing ? 'input-disabled' : ''} />
                            <input type="password" placeholder="Senha" value={userForm.password} onChange={e => setUserForm({ ...userForm, password: e.target.value })} />
                            <div className="modal-actions">
                                <button type="button" onClick={() => setShowUserModal(false)} className="btn btn-secondary">Cancelar</button>
                                <button type="submit" className="btn btn-primary">Salvar</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* MODAL CONFIGURAÇÕES */}
            {showSettingsModal && (
                <div className="modal-overlay">
                    <div className="modal-content">
                        <div className="modal-header"><h3>Configurações da Empresa</h3><button onClick={() => setShowSettingsModal(false)} className="close-btn"><Icons.X /></button></div>
                        <form onSubmit={handleSaveSettings} className="modal-form">
                            <label>Nome de Exibição</label>
                            <input type="text" value={companySettings.name} onChange={e => setCompanySettings({ ...companySettings, name: e.target.value })} />
                            <label>Telefone de Contato</label>
                            <input type="text" placeholder="+55..." value={companySettings.phone} onChange={e => setCompanySettings({ ...companySettings, phone: e.target.value })} />
                            <button type="submit" className="btn btn-primary full-width">Salvar Alterações</button>
                        </form>
                    </div>
                </div>
            )}

            {/* MODAL DETALHES */}
            {selectedUser && (
                <div className="modal-overlay" onClick={() => setSelectedUser(null)}>
                    <div className="modal-content modal-large" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <div className="user-detail-header">
                                <div className="user-avatar-lg">{getInitials(selectedUser.full_name)}</div>
                                <div><h3>{selectedUser.full_name}</h3><p className="text-mono">@{selectedUser.username}</p></div>
                            </div>
                            <button onClick={() => setSelectedUser(null)} className="close-btn"><Icons.X /></button>
                        </div>
                        <div className="user-stats-grid">
                            <div className="stat-box"><span>Clientes</span><strong>{selectedUser.metrics.clients_month}</strong></div>
                            <div className="stat-box"><span>Tempo</span><strong>{selectedUser.metrics.response}</strong></div>
                            <div className="stat-box highlight"><span>Uso IA</span><strong>{formatNumber(selectedUser.metrics.ai_usage)}</strong></div>
                        </div>
                        <div className="charts-row">
                            <div className="chart-container">
                                <h4>Distribuição de Mensagens</h4>
                                <div className="pie-chart-wrapper">
                                    <div className="pie-chart" style={{
                                        background: `conic-gradient(#3b82f6 0% ${selectedUser.metrics.pie.text}%, #22c55e ${selectedUser.metrics.pie.text}% ${selectedUser.metrics.pie.text + selectedUser.metrics.pie.audio}%, #a855f7 ${selectedUser.metrics.pie.text + selectedUser.metrics.pie.audio}% ${selectedUser.metrics.pie.text + selectedUser.metrics.pie.audio + selectedUser.metrics.pie.image}%, #f59e0b ${selectedUser.metrics.pie.text + selectedUser.metrics.pie.audio + selectedUser.metrics.pie.image}% 100%)`
                                    }}></div>
                                    <div className="chart-legend"><div><span className="dot blue"></span> Texto</div><div><span className="dot green"></span> Áudio</div><div><span className="dot purple"></span> Imagem</div><div><span className="dot orange"></span> Vídeo</div></div>
                                </div>
                            </div>
                            <div className="msg-breakdown">
                                <div className="breakdown-item"><Icons.MsgText /> Texto <span>{selectedUser.metrics.messages.text}</span></div>
                                <div className="breakdown-item"><Icons.MsgAudio /> Áudio <span>{selectedUser.metrics.messages.audio}</span></div>
                                <div className="breakdown-item"><Icons.MsgImage /> Mídia <span>{selectedUser.metrics.messages.image + selectedUser.metrics.messages.video}</span></div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ManagementPage;
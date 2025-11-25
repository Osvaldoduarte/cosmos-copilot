import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useNavigate } from 'react-router-dom';
import '../styles/admin.css';

// Ícones
const Icons = {
    Building: () => <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /></svg>,
    Plus: () => <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>,
    Users: () => <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>,
    Server: () => <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" /></svg>,
    Trash: () => <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>,
    Settings: () => <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>,
    X: () => <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>,
    AlertTriangle: () => <svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
};

const Toast = ({ message, type, onClose }) => {
    useEffect(() => { const t = setTimeout(onClose, 4000); return () => clearTimeout(t); }, [onClose]);
    return ( <div className={`custom-toast ${type}`}> {type === 'success' ? '✔' : '✖'} <span>{message}</span> </div> );
};

const AdminPage = () => {
    const { token, handleLogout } = useAuth();
    const navigate = useNavigate();
    const [data, setData] = useState(null);
    const [notification, setNotification] = useState(null);

    // Modais
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [selectedTenant, setSelectedTenant] = useState(null);
    const [showGlobalUsersModal, setShowGlobalUsersModal] = useState(false); // ✨ NOVO ESTADO
    const [globalUsersList, setGlobalUsersList] = useState([]); // ✨ LISTA GLOBAL

    // Confirmação
    const [confirmation, setConfirmation] = useState({ isOpen: false, title: '', message: '', action: null });

    // Forms
    const [newTenant, setNewTenant] = useState({ company_name: '', company_slug: '', admin_username: '', admin_password: '' });
    const [newUser, setNewUser] = useState({ username: '', password: '', full_name: '' });

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [loading, setLoading] = useState(true);
    const [tenantUsers, setTenantUsers] = useState([]);
    const [activeTab, setActiveTab] = useState('info');

    const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
    const notify = (msg, type = 'success') => setNotification({ message: msg, type });

    // --- FETCH DATA ---
    const fetchAdminData = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/admin/dashboard`, { headers: { 'Authorization': `Bearer ${token}` } });
            if (response.status === 403) { navigate('/'); return; }
            const result = await response.json();
            setData(result);
        } catch (error) { console.error(error); } finally { setLoading(false); }
    }, [token, navigate, API_URL]);

    // ✨ FETCH DE TODOS OS USUÁRIOS
    const fetchAllGlobalUsers = async () => {
        try {
            const res = await fetch(`${API_URL}/admin/users_global`, { headers: { 'Authorization': `Bearer ${token}` } });
            if (res.ok) {
                const list = await res.json();
                setGlobalUsersList(list);
                setShowGlobalUsersModal(true);
            }
        } catch (e) { notify("Erro ao buscar usuários", "error"); }
    };

    const fetchTenantUsers = async (tenantId) => {
        try {
            const res = await fetch(`${API_URL}/admin/tenants/${tenantId}/users`, { headers: { 'Authorization': `Bearer ${token}` } });
            if (res.ok) setTenantUsers(await res.json());
        } catch (e) { console.error(e); }
    };

    useEffect(() => { fetchAdminData(); }, [fetchAdminData]);

    // --- ACTIONS ---
    const executeDeleteTenant = async (tenantId) => {
        try {
            const res = await fetch(`${API_URL}/admin/tenants/${tenantId}`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${token}` } });
            if(res.ok) { notify("Empresa excluída", "success"); fetchAdminData(); }
            else { notify("Erro ao excluir", "error"); }
        } catch(e) { notify("Erro de rede", "error"); }
    };

    const executeDeleteUser = async (username, isGlobal = false) => {
        try {
            const res = await fetch(`${API_URL}/admin/users/${username}`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${token}` } });
            if (res.ok) {
                 // Atualiza lista local dependendo de onde veio
                 if (isGlobal) {
                     setGlobalUsersList(prev => prev.filter(u => u.username !== username));
                     // Atualiza contagem
                     fetchAdminData();
                 } else {
                     setTenantUsers(prev => prev.filter(u => u.username !== username));
                 }
                 notify("Usuário removido.", "success");
            } else { notify("Erro ao deletar", "error"); }
        } catch (e) { notify("Erro de rede", "error"); }
    };

    const confirmDeleteUser = (username, isGlobal = false) => {
        setConfirmation({
            isOpen: true,
            title: 'Remover Usuário?',
            message: `Tem certeza que deseja remover o acesso de "${username}"?`,
            action: () => executeDeleteUser(username, isGlobal)
        });
    };

    const confirmDeleteTenant = (tenantId) => {
        setConfirmation({ isOpen: true, title: 'Excluir Empresa?', message: `Você está prestes a apagar a empresa "${tenantId}" e TODOS os seus dados.`, action: () => executeDeleteTenant(tenantId) });
    };

    const handleConfirmAction = () => { if (confirmation.action) confirmation.action(); setConfirmation({ ...confirmation, isOpen: false }); };

    const handleCreateTenant = async (e) => {
        e.preventDefault(); setIsSubmitting(true);
        try {
            const response = await fetch(`${API_URL}/admin/create_tenant`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` }, body: JSON.stringify(newTenant) });
            if (response.ok) { notify("Empresa criada!", "success"); setShowCreateModal(false); setNewTenant({ company_name: '', company_slug: '', admin_username: '', admin_password: '' }); fetchAdminData(); }
            else { notify("Erro ao criar", "error"); }
        } catch (error) { notify("Erro conexão", "error"); } finally { setIsSubmitting(false); }
    };

    const handleAddUserToTenant = async (e) => {
        e.preventDefault(); if (!selectedTenant) return;
        try {
            const res = await fetch(`${API_URL}/admin/tenants/${selectedTenant.id}/users`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` }, body: JSON.stringify(newUser) });
            if (res.ok) { setNewUser({ username: '', password: '', full_name: '' }); fetchTenantUsers(selectedTenant.id); notify("Usuário adicionado!", "success"); }
            else { notify("Erro ao adicionar", "error"); }
        } catch (e) { notify("Erro", "error"); }
    };

    const handleOpenManage = (tenant) => { setSelectedTenant(tenant); setTenantUsers([]); setActiveTab('info'); fetchTenantUsers(tenant.id); };

    if (loading) return <div className="loading-screen"><div className="spinner-dot"></div></div>;

    return (
        <div className="admin-container">
            {notification && <Toast message={notification.message} type={notification.type} onClose={() => setNotification(null)} />}

            <header className="admin-header">
                <div className="header-left"><h1>Cosmos Admin</h1><span className="badge-admin">SUPER USER</span></div>
                <button onClick={handleLogout} className="btn-logout">Sair</button>
            </header>

            <div className="admin-content">
                <div className="kpi-row">
                    <div className="kpi-card">
                        <div className="kpi-icon blue"><Icons.Building /></div>
                        <div className="kpi-info"><h3>{data?.metrics.total_tenants}</h3><p>Empresas</p></div>
                    </div>

                    {/* ✨ CARD CLICÁVEL DE USUÁRIOS */}
                    <div className="kpi-card clickable" onClick={fetchAllGlobalUsers} title="Clique para ver lista completa">
                        <div className="kpi-icon purple"><Icons.Users /></div>
                        <div className="kpi-info">
                            <h3>{data?.metrics.total_users}</h3>
                            <p>Usuários (Equipe)</p>
                        </div>
                    </div>

                    <div className="kpi-card">
                        <div className="kpi-icon green"><Icons.Server /></div>
                        <div className="kpi-info"><h3>{data?.metrics.active_instances}</h3><p>Instâncias Online</p></div>
                    </div>
                </div>

                <div className="admin-section">
                    <div className="section-header">
                        <h2>Gerenciamento de Empresas</h2>
                        <button onClick={() => setShowCreateModal(true)} className="btn-primary-glow"><Icons.Plus /> Nova Empresa</button>
                    </div>
                    <div style={{overflowX: 'auto'}}>
                        <table className="admin-table">
                            <thead><tr><th>Empresa</th><th>ID (Slug)</th><th>Instância</th><th>Status</th><th style={{textAlign: 'right'}}>Ações</th></tr></thead>
                            <tbody>
                                {data?.tenants.map(t => (
                                    <tr key={t.id}>
                                        <td><strong>{t.name}</strong></td>
                                        <td className="mono">{t.id}</td>
                                        <td className="mono">{t.instance}</td>
                                        <td><span className="status-dot online"></span> Ativo</td>
                                        <td className="actions-cell">
                                            <button onClick={() => handleOpenManage(t)} className="btn-icon" title="Gerenciar"><Icons.Settings /></button>
                                            <button onClick={() => confirmDeleteTenant(t.id)} className="btn-icon danger" title="Excluir"><Icons.Trash /></button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {/* ✨ MODAL GLOBAL DE USUÁRIOS */}
            {showGlobalUsersModal && (
                <div className="modal-backdrop">
                    <div className="modal-panel large glass-effect">
                        <div className="modal-header">
                            <div><h3>Todos os Usuários</h3><p className="subtitle">Listagem global (exceto admins)</p></div>
                            <button onClick={() => setShowGlobalUsersModal(false)}><Icons.X /></button>
                        </div>
                        <div className="table-container-scroll" style={{maxHeight: '500px'}}>
                            <table className="users-table">
                                <thead><tr><th>Usuário</th><th>Nome</th><th>Empresa</th><th>Ação</th></tr></thead>
                                <tbody>
                                    {globalUsersList.map(u => (
                                        <tr key={u.username}>
                                            <td style={{color: '#cbd5e1'}}>{u.username}</td>
                                            <td>{u.full_name}</td>
                                            <td><span className="badge-admin" style={{fontSize: '0.7rem', background: 'rgba(59,130,246,0.2)', color: '#93c5fd'}}>{u.tenant_name}</span></td>
                                            <td><button onClick={() => confirmDeleteUser(u.username, true)} className="btn-small-danger">Remover</button></td>
                                        </tr>
                                    ))}
                                    {globalUsersList.length === 0 && <tr><td colSpan="4" style={{textAlign: 'center', padding: '20px'}}>Nenhum usuário da equipe encontrado.</td></tr>}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}

            {/* MODAL DE GERENCIAMENTO DE EMPRESA */}
            {selectedTenant && (
                <div className="modal-backdrop">
                    <div className="modal-panel large glass-effect">
                        <div className="modal-header"><div><h3>{selectedTenant.name}</h3><p className="subtitle">{selectedTenant.id}</p></div><button onClick={() => setSelectedTenant(null)}><Icons.X /></button></div>
                        <div className="modal-tabs">
                            <button className={activeTab === 'info' ? 'active' : ''} onClick={() => setActiveTab('info')}>Info</button>
                            <button className={activeTab === 'users' ? 'active' : ''} onClick={() => setActiveTab('users')}>Usuários</button>
                        </div>
                        <div className="modal-body">
                            {activeTab === 'info' && ( <div className="info-tab"><label>Nome da Empresa</label><input defaultValue={selectedTenant.name} disabled className="input-disabled" /><label style={{marginTop: '10px'}}>Instância Evolution</label><input defaultValue={selectedTenant.instance} disabled className="input-disabled mono" /></div> )}
                            {activeTab === 'users' && (
                                <div className="users-tab">
                                    <div className="table-container-scroll">
                                        <table className="users-table">
                                            <thead><tr><th>Usuário</th><th>Nome</th><th>Ação</th></tr></thead>
                                            <tbody>
                                                {tenantUsers.map(u => (
                                                    <tr key={u.username}><td>{u.username}</td><td>{u.full_name}</td><td><button onClick={() => confirmDeleteUser(u.username)} className="btn-small-danger">Remover</button></td></tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                    <form onSubmit={handleAddUserToTenant} className="add-user-box">
                                        <h4>Adicionar Novo Usuário</h4>
                                        <div className="grid-inputs">
                                            <input placeholder="Username" required value={newUser.username} onChange={e => setNewUser({...newUser, username: e.target.value})} />
                                            <input placeholder="Nome Completo" required value={newUser.full_name} onChange={e => setNewUser({...newUser, full_name: e.target.value})} />
                                            <input placeholder="Senha" type="password" required value={newUser.password} onChange={e => setNewUser({...newUser, password: e.target.value})} />
                                        </div>
                                        <button type="submit" className="btn-primary-glow full-width mt-2">Adicionar à Equipe</button>
                                    </form>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* MODAL CRIAÇÃO */}
            {showCreateModal && (
                <div className="modal-backdrop">
                    <div className="modal-panel">
                        <div className="modal-header"><h3>Nova Empresa</h3><button onClick={() => setShowCreateModal(false)}><Icons.X /></button></div>
                        <form onSubmit={handleCreateTenant}>
                            <input placeholder="Nome da Empresa" required value={newTenant.company_name} onChange={e => setNewTenant({...newTenant, company_name: e.target.value})} />
                            <input placeholder="ID (Slug)" required value={newTenant.company_slug} onChange={e => setNewTenant({...newTenant, company_slug: e.target.value})} />
                            <div style={{borderTop: '1px solid #334155', margin: '10px 0', paddingTop: '10px', color: '#94a3b8', fontSize: '0.8rem'}}>ADMIN INICIAL</div>
                            <input placeholder="Usuário Admin" required value={newTenant.admin_username} onChange={e => setNewTenant({...newTenant, admin_username: e.target.value})} />
                            <input placeholder="Senha" type="password" required value={newTenant.admin_password} onChange={e => setNewTenant({...newTenant, admin_password: e.target.value})} />
                            <button type="submit" className="btn-primary-glow full-width" disabled={isSubmitting}>Criar Sistema</button>
                        </form>
                    </div>
                </div>
            )}

            {/* CONFIRMATION MODAL */}
            {confirmation.isOpen && (
                <div className="modal-backdrop" style={{zIndex: 1100}}>
                    <div className="modal-panel mini glass-effect">
                        <div className="confirm-icon"><Icons.AlertTriangle /></div>
                        <h3>{confirmation.title}</h3>
                        <p style={{color: '#cbd5e1', marginTop: '10px', lineHeight: '1.5'}}>{confirmation.message}</p>
                        <div className="modal-actions">
                            <button className="btn-secondary" onClick={() => setConfirmation({...confirmation, isOpen: false})}>Cancelar</button>
                            <button className="btn-danger-solid" onClick={handleConfirmAction}>Confirmar</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default AdminPage;
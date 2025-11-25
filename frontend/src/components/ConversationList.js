import React from 'react';
import { useNavigate } from 'react-router-dom';
import '../styles/sidebar.css';

// 👇 AQUI: Recebemos 'onNewChat' que vem do MainLayout
const ConversationList = ({ onLogout, onNewChat }) => {
    const navigate = useNavigate();

    return (
        <div className="conversation-list-panel">

            {/* CABEÇALHO */}
            <div className="conversation-list-header">
                <h3>Conversas</h3>

                {/* 👇 AQUI: O botão chama a função que veio do pai */}
                <button
                    className="new-chat-btn"
                    onClick={onNewChat}
                    title="Nova Conversa"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                    </svg>
                </button>
            </div>

            {/* BARRA DE BUSCA */}
            <div className="search-bar">
                <div className="search-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                </div>
                <input type="text" placeholder="Buscar conversa..." />
            </div>

            {/* LISTA (Vazia ou com itens) */}
            <div className="conversation-list">
                {/* Aqui virão os itens mapeados do contexto depois */}
                <div style={{ padding: '20px', textAlign: 'center', color: '#7d8590', fontSize: '0.9rem' }}>
                    Nenhuma conversa iniciada.
                </div>
            </div>

      <div className="conversation-list-footer">
        {/* Botão Manager (Azul) */}
        <button
            onClick={() => navigate('/manager')}
            className="footer-btn btn-manager"
            title="Painel Gerencial"
        >
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="7" height="7"></rect>
                <rect x="14" y="3" width="7" height="7"></rect>
                <rect x="14" y="14" width="7" height="7"></rect>
                <rect x="3" y="14" width="7" height="7"></rect>
            </svg>
            <span>Gerencial</span>
        </button>

        {/* Botão Sair (Vermelho) */}
        <button onClick={onLogout} className="footer-btn btn-logout">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                <polyline points="16 17 21 12 16 7"></polyline>
                <line x1="21" y1="12" x2="9" y2="12"></line>
            </svg>
            <span>Sair</span>
        </button>
      </div>
    </div>
  );
}

export default ConversationList;
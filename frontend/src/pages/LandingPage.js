import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import '../styles/landing.css';

const CheckIcon = () => <svg className="icon-check" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>;

const LandingPage = () => {
    const navigate = useNavigate();
    const { isAuthenticated } = useAuth();

    // --- LÓGICA DOS CENÁRIOS ---
    // --- LÓGICA DOS CENÁRIOS (Texto corrigido para não prever o futuro) ---
    const scenarios = [
        {
            industry: "Concessionária",
            ragType: "Playbook de Vendas",
            // 1. Vendedor apenas cumprimenta
            sellerGreeting: "Bom dia! Tudo bem? Em que posso ajudar?",
            // 2. Cliente faz a pergunta
            clientQuestion: "O Civic 2021 ainda tá disponível? Aceita troca?",
            // 3. IA Analisa
            aiThinking: "Consultando estoque e regras de troca...",
            aiSuggestion: "Sim! Ele está no pátio. Aceitamos troca sim. Consegue trazer o carro hoje às 16h para avaliarmos?",
            aiAction: "Sugerir Agendamento",
            // 4. Resposta Final
            finalMsg: "Sim! Ele está no pátio. Aceitamos troca sim. Consegue trazer o carro hoje às 16h para avaliarmos?"
        },
        {
            industry: "Climatização",
            ragType: "Manual Técnico",
            sellerGreeting: "Bom dia, tudo bem contigo?",
            clientQuestion: "Preciso climatizar uma sala de 40m², qual recomenda?",
            aiThinking: "Calculando carga térmica (40m² x 600 BTUs)...",
            aiSuggestion: "Para 40m², o cálculo técnico indica 24.000 BTUs. Recomendo o modelo Inverter, que economiza até 40% de energia.",
            aiAction: "Ofertar Produto Técnico",
            finalMsg: "Para 40m², o cálculo técnico indica 24.000 BTUs. Recomendo o modelo Inverter, que economiza até 40% de energia."
        },
        {
            industry: "Atacado de Makes",
            ragType: "Base de Conhecimento",
            sellerGreeting: "Olá, bom dia! ",
            clientQuestion: "Qual o pedido mínimo pra CNPJ? Tem catálogo?",
            aiThinking: "Verificando política comercial atualizada...",
            aiSuggestion: "O pedido mínimo é super acessível: R$ 500,00! Vou te enviar o catálogo em PDF. Já tem cadastro conosco?",
            aiAction: "Enviar Catálogo",
            finalMsg: "O pedido mínimo é super acessível: R$ 500,00! Vou te enviar o catálogo em PDF. Já tem cadastro conosco?"
        }
    ];

    const [scenarioIndex, setScenarioIndex] = useState(0);
    const active = scenarios[scenarioIndex];

    // Troca de cenário a cada 16s (tempo exato da animação CSS)
    useEffect(() => {
        const interval = setInterval(() => {
            setScenarioIndex((prev) => (prev + 1) % scenarios.length);
        }, 16000);
        return () => clearInterval(interval);
    }, []);

    const handleCtaClick = () => {
        if (isAuthenticated) navigate('/app');
        else navigate('/login');
    };

    return (
        <div className="landing-wrapper">
            <nav className="landing-nav">
                <div className="nav-logo">
                    <div className="logo-symbol"></div>
                    <span className="logo-text">Cosmos Copilot</span>
                </div>
                <div className="nav-actions">
                    <button onClick={() => navigate(isAuthenticated ? '/app' : '/login')} className="btn-login-outline">
                        {isAuthenticated ? 'Ir para o App' : 'Login'}
                    </button>
                    <button onClick={handleCtaClick} className="btn-cta-small">Começar</button>
                </div>
            </nav>

            <header className="hero-section">
                <div className="hero-content">
                    <div className="badge-anti-bot">Chega de respostas genéricas</div>
                    <h1 className="hero-title">
                        Não somos um Chatbot.<br />
                        Somos a <span className="text-gradient">Super Mente</span> do seu Vendedor.
                    </h1>
                    <p className="hero-subtitle">
                        O Cosmos é uma <strong>IA Copiloto</strong> que lê seus manuais técnicos, entende o contexto da conversa e sopra a resposta perfeita no ouvido da sua equipe, garantindo atendimento humanizado e tecnicamente impecável.
                    </p>
                    <div className="hero-buttons">
                        <button onClick={handleCtaClick} className="btn-cta-large">Quero Potencializar meu Time</button>
                    </div>
                    {/* Stats mantidos */}
                </div>

                <div className="hero-visual">
                    <div className="glass-mockup animated-mockup" key={scenarioIndex}>
                        <div className="mockup-header">
                            <div className="dots"><span></span><span></span><span></span></div>
                            <div className="mockup-title">Cosmos Copilot • {active.industry}</div>
                        </div>

                        <div className="mockup-body-animated">
                            {/* 1. Cliente Cumprimenta */}
                            <div className="msg-anim msg-client-1">Bom dia!</div>

                            {/* 2. Vendedor Cumprimenta (Genérico) */}
                            <div className="msg-anim msg-seller-1">{active.sellerGreeting}</div>

                            {/* 3. Cliente faz a Pergunta Difícil */}
                            <div className="msg-anim msg-client-2">{active.clientQuestion}</div>

                            {/* Animações de Ação */}
                            <div className="cursor-pointer">
                                <svg viewBox="0 0 24 24" fill="white" stroke="black" strokeWidth="1"><path d="M5.5 3.21V20.8c0 .45.54.67.85.35l4.86-4.86a.5.5 0 0 1 .35-.15h6.87a.45.45 0 0 0 .35-.8l-12.4-12.8a.45.45 0 0 0-.88.66Z"/></svg>
                            </div>

                            <div className="context-menu">
                                <div className="menu-item"><span className="icon"></span></div>
                                <div className="menu-item active"><span className="icon">⚛</span> Consultar Cosmos</div>
                            </div>

                            <div className="ai-loading-indicator">
                                <div className="thinking-dots"><span></span><span></span><span></span></div>
                                <span className="thinking-text">
                                    {active.aiThinking} <br/>
                                    <span style={{opacity:0.7, fontSize:'0.65rem'}}>Fonte: {active.ragType}</span>
                                </span>
                            </div>

                            <div className="ai-suggestion-card">
                                <div className="ai-card-header">Sugestão de resposta:</div>
                                <div className="ai-card-text">"{active.aiSuggestion}"</div>
                                <div className="ai-card-actions">
                                    <button className="btn-fake-send">{active.aiAction}</button>
                                </div>
                            </div>

                            {/* 4. Resposta Final Técnica */}
                            <div className="msg-anim msg-seller-final">{active.finalMsg}</div>
                        </div>
                        <div className="glow-effect"></div>
                    </div>
                </div>
            </header>

            <section className="features-section">
                <h2 className="section-title">O cérebro que se adapta ao seu negócio</h2>
                <div className="features-grid">
                    <div className="feature-card">
                        <div className="feature-icon blue">🚗</div>
                        <h3>Vendas Complexas</h3>
                        <p>Ideal para carros, imóveis e seguros. A IA entende o momento da negociação e sugere o fechamento.</p>
                    </div>
                    <div className="feature-card">
                        <div className="feature-icon purple">❄️</div>
                        <h3>Técnico e Preciso</h3>
                        <p>Ar condicionado, peças ou TI? Suba seus manuais PDF e o Cosmos vira um engenheiro especialista.</p>
                    </div>
                    <div className="feature-card">
                        <div className="feature-icon green">💄</div>
                        <h3>Atacado e Varejo</h3>
                        <p>Tabela de preços, política de frete e catálogo? O Cosmos tem tudo na ponta da língua.</p>
                    </div>
                </div>
            </section>

            <section className="cta-section">
                <div className="cta-box">
                    <h2>Sua equipe com superpoderes.</h2>
                    <p>Experimente a inteligência que converte conversas em contratos.</p>
                    <button onClick={handleCtaClick} className="btn-cta-large">Criar Conta Grátis</button>
                </div>
            </section>

            <footer className="landing-footer"><p>© 2025 Cosmos Copilot.</p></footer>
        </div>
    );
};

export default LandingPage;
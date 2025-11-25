import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { Link } from 'react-router-dom';
import '../styles/login.css';

// Ícones
const ArrowLeftIcon = () => (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>);
const LoginIcon = () => (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg>);
const CosmosLogo = ({ size = 50 }) => (<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2a3 3 0 0 0-3 3v1a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 11h-2"/><path d="M5 11H3"/><path d="M12 18a3 3 0 0 0 3 3h1a3 3 0 0 0 3-3v-1a3 3 0 0 0-3-3h-1v4Z"/><path d="M12 18a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3v-1a3 3 0 0 1 3-3h1v4Z"/><path d="M12 8v4"/></svg>);

function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Efeito de saída visual apenas (opcional, mantendo simples)
  const [isExiting, setIsExiting] = useState(false);

  const { handleLogin } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const success = await handleLogin(username, password);
      if (success) {
        setIsExiting(true);
      } else {
        setError('Acesso negado. Verifique suas credenciais.');
        setIsLoading(false);
      }
    } catch (err) {
      console.error("Erro no login:", err);
      setError('Erro de conexão com o Cosmos.');
      setIsLoading(false);
    }
  };

  return (
    <div className="login-page-wrapper">

      {/* --- LADO ESQUERDO: FORMULÁRIO --- */}
      <div className={`login-section-form ${isExiting ? 'fade-out' : ''}`}>

        {/* Botão Voltar */}
        <Link to="/" className="back-to-home">
          <ArrowLeftIcon /> Voltar para Home
        </Link>

        <div className="login-header">
          <div style={{ color: '#3b82f6', display: 'inline-block', marginBottom: '10px' }}>
             <CosmosLogo size={60} />
          </div>
          <h1>Bem-vindo de volta</h1>
          <p>Acesse seu painel de controle neural.</p>
        </div>

        <form onSubmit={handleSubmit} className="cosmos-input-group">
          <div>
            <input
                type="text"
                className="cosmos-input"
                placeholder="Usuário / E-mail"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={isLoading}
                required
                autoFocus
            />
          </div>

          <div>
            <input
                type="password"
                className="cosmos-input"
                placeholder="Sua senha"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
                required
            />
          </div>

          {error && (
            <div style={{ color: '#f85149', fontSize: '0.9rem', background: 'rgba(248, 81, 73, 0.1)', padding: '10px', borderRadius: '8px', textAlign: 'center' }}>
              {error}
            </div>
          )}

          <button type="submit" className="btn-cosmos-primary" disabled={isLoading}>
            {isLoading ? (
                <><div className="spinner-dot"></div> Conectando...</>
            ) : (
                <><LoginIcon /> Acessar Sistema</>
            )}
          </button>

          <div style={{ textAlign: 'center', marginTop: '1rem', fontSize: '0.85rem', color: '#64748b' }}>
            Esqueceu a senha? <span style={{ color: '#3b82f6', cursor: 'pointer' }}>Contate o admin</span>
          </div>
        </form>

        {/* Fundo animado sutil apenas no lado do form (opcional) */}
        <div className="animated-background-lines" style={{opacity: 0.1, zIndex: -1}}>
            <div className="line"></div><div className="line"></div><div className="line"></div>
        </div>
      </div>

      {/* --- LADO DIREITO: BRANDING & CONTEXTO --- */}
      <div className="login-section-visual">
        <div className="glow-orb orb-1"></div>
        <div className="glow-orb orb-2"></div>

        <div className="visual-content">
            {/* Exemplo de "Feature Tag" */}
            <div style={{
                display: 'inline-block',
                padding: '6px 12px',
                borderRadius: '20px',
                background: 'rgba(59, 130, 246, 0.1)',
                border: '1px solid rgba(59, 130, 246, 0.3)',
                color: '#60a5fa',
                fontSize: '0.8rem',
                fontWeight: '600',
                marginBottom: '1.5rem'
            }}>
                COSMOS V2.0
            </div>

            <h2 className="visual-tagline">
                Inteligência que <br/>potencializa vendas.
            </h2>
            <p className="visual-description">
                Gerencie seus atendimentos, monitore métricas em tempo real e deixe nossa IA cuidar da rotina pesada. O futuro do seu negócio começa aqui.
            </p>

            {/* Pequeno elemento visual extra (Card Flutuante Decorativo) */}
            <div style={{
                marginTop: '3rem',
                background: 'rgba(30, 41, 59, 0.4)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '12px',
                padding: '15px',
                display: 'flex',
                alignItems: 'center',
                gap: '15px',
                backdropFilter: 'blur(5px)'
            }}>
                <div style={{ background: '#22c55e', width: '10px', height: '10px', borderRadius: '50%', boxShadow: '0 0 10px #22c55e' }}></div>
                <div style={{ fontSize: '0.9rem', color: '#cbd5e1' }}>
                    <strong>Status do Sistema:</strong> Todos os neurônios operacionais.
                </div>
            </div>
        </div>
      </div>

    </div>
  );
}

export default Login;
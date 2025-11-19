import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';

const LoginIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M10 20H6V4h4v2H8v12h2v2zm10-4h-4V8h4v8zm-2 0h-2V8h2v8zm-5-1H11V9h4v6zm-2-4h-2V9h2v2z"/></svg>);
const CosmosLogo = () => (<svg width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2a3 3 0 0 0-3 3v1a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 11h-2"/><path d="M5 11H3"/><path d="M12 18a3 3 0 0 0 3 3h1a3 3 0 0 0 3-3v-1a3 3 0 0 0-3-3h-1v4Z"/><path d="M12 18a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3v-1a3 3 0 0 1 3-3h1v4Z"/><path d="M12 8v4"/></svg>);

function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isExiting, setIsExiting] = useState(false);

  // ✨ Pega handleLogin corretamente
  const { handleLogin } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      // ✨ Usa handleLogin e espera o resultado
      const success = await handleLogin(username, password);
      if (success) {
        setIsExiting(true);
      } else {
        setError('Credenciais inválidas.');
        setIsLoading(false);
      }
    } catch (err) {
      console.error("Erro no login:", err);
      setError('Erro ao tentar logar.');
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className={`login-card glass-effect ${isExiting ? 'fade-out-up' : ''}`}>
        <div className="login-logo"><CosmosLogo /></div>
        <h2>Cosmos Copilot</h2>
        <form onSubmit={handleSubmit} className="login-form">
          <input type="text" placeholder="Usuário" value={username} onChange={(e) => setUsername(e.target.value)} disabled={isLoading} required />
          <input type="password" placeholder="Senha" value={password} onChange={(e) => setPassword(e.target.value)} disabled={isLoading} required />
          <button type="submit" disabled={isLoading}>
            {isLoading ? <><div className="spinner-dot"></div>Entrando...</> : <><LoginIcon />Entrar</>}
          </button>
          {error && <p className="login-error">{error}</p>}
        </form>
      </div>
      <div className="animated-background-lines">
          <div className="line"></div><div className="line"></div><div className="line"></div><div className="line"></div><div className="line"></div>
      </div>
    </div>
  );
}

export default Login;
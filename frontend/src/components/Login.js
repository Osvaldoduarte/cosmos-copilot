import React, { useState } from 'react';

// Um ícone de "brilho/IA" para representar o Copilot
const CopilotLogo = () => (
  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M12 2L9 9L2 12L9 15L12 22L15 15L22 12L15 9L12 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M5 2L6 5L9 6L6 7L5 10L4 7L1 6L4 5L5 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

function Login({ onLogin, error, isLoading }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    onLogin(username, password);
  };

  return (
    <div className="login-page">
      {/* Coluna da Esquerda: Branding */}
      <div className="login-branding">
        <div className="branding-content">
          <CopilotLogo />
          <h1>VENAI</h1>
          <p>Sua central de vendas inteligente.</p>
        </div>
      </div>

      {/* Coluna da Direita: Formulário */}
      <div className="login-form-wrapper">
        <form className="login-form" onSubmit={handleSubmit}>
          <h2>Acesse sua conta</h2>
          <p>Bem-vindo de volta! Por favor, insira seus dados.</p>

          <div className="input-group">
            <label htmlFor="username">Usuário</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              disabled={isLoading}
            />
          </div>

          <div className="input-group">
            <label htmlFor="password">Senha</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={isLoading}
            />
          </div>

          {error && <p className="login-error-message">{error}</p>}

          <button type="submit" className="login-button" disabled={isLoading}>
            {isLoading ? 'Entrando...' : 'Entrar'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default Login;
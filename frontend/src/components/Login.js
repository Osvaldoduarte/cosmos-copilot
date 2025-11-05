import React, { useState } from 'react';

// Um ícone de "brilho/IA" para representar o Copilot (Restaurado)
const CopilotLogo = () => (
  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M12 2L9 9L2 12L9 15L12 22L15 15L22 12L15 9L12 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M5 2L6 5L9 6L6 7L5 10L4 7L1 6L4 5L5 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);


function Login({ onLogin, error, isLoading }) {

  // --- CORREÇÃO: Define o estado para os inputs ---
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  // Handler para o envio do formulário
  const handleSubmit = (e) => {
    e.preventDefault(); // Impede o recarregamento da página
    if (!isLoading) {
      // Chama a função 'handleLogin' (do useAuth)
      onLogin(username, password);
    }
  };

  // O JSX (HTML) do seu formulário de login
  return (
    <div className="login-container">
      <div className="login-box">

        {/* CORREÇÃO: Restaurando o ícone "tech" e o título */}
        <div className="login-header">
            <CopilotLogo />
            <h2>Cosmos Copilot</h2>
        </div>


        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <label htmlFor="username">Usuário (Email)</label>
            <input
              type="text"
              id="username"
              value={username} // Controlado pelo estado
              onChange={(e) => setUsername(e.target.value)} // Atualiza o estado
              required
            />
          </div>

          <div className="input-group">
            <label htmlFor="password">Senha</label>
            <input
              type="password"
              id="password"
              value={password} // Controlado pelo estado
              onChange={(e) => setPassword(e.target.value)} // Atualiza o estado
              required
            />
          </div>

          {/* Exibe o erro 401 vindo do useAuth */}
          {error && <div className="error-message">{error}</div>}

          <button type="submit" className="login-button" disabled={isLoading}>
            {isLoading ? 'Carregando...' : 'Entrar'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default Login;
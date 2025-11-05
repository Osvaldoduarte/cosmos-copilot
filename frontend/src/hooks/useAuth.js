// Em frontend/src/hooks/useAuth.js (ou context/AuthContext.js)
// (ADICIONE o 'export AuthProvider' se estiver faltando)

import React, { useState, useEffect, useCallback, createContext, useContext } from 'react';
import api from '../services/api';

// 💡 PASSO 1: Crie o Contexto
const AuthContext = createContext(null);

// 💡 PASSO 2: Crie o Hook (como você já tinha)
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth deve ser usado dentro de um AuthProvider");
  }
  return context;
}

// 💡 PASSO 3: Crie o Provider (A PARTE QUE FALTAVA EXPORTAR)
export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem('authToken'));
  const [user, setUser] = useState(null);
  const [instanceConnected, setInstanceConnected] = useState(false);
  const [isLoginLoading, setIsLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState('');
  const [isStatusLoading, setIsStatusLoading] = useState(true);

  useEffect(() => {
    const checkInstanceStatus = async () => {
      if (token) {
        setIsStatusLoading(true);
        try {
          const { data } = await api.get('/evolution/instance/status');
          if (data.instance && data.instance.state === 'open') {
            setInstanceConnected(true);
          } else {
            setInstanceConnected(false);
          }
        } catch (err) {
          console.error("Erro ao verificar status, desconectando:", err);
          handleLogout(); // Força o logout se o token for inválido
        } finally {
          setIsStatusLoading(false);
        }
      } else {
        setIsStatusLoading(false); // Sem token, não há o que carregar
      }
    };
    checkInstanceStatus();
  }, [token]); // 'handleLogout' não precisa ser dependência aqui

  const handleLogin = useCallback(async (username, password) => {
    // (Sua lógica de login...)
    setIsLoginLoading(true);
    setLoginError(null);
    try {
      const formData = new FormData();
      formData.append('username', username);
      formData.append('password', password);
      const { data } = await api.post('/token', formData);
      if (data && data.access_token) {
        const newToken = data.access_token;
        localStorage.setItem('authToken', newToken);
        setToken(newToken);
      } else {
        throw new Error("Resposta de login inválida.");
      }
    } catch (err) {
      setLoginError('Usuário ou senha inválidos.');
    }
    setIsLoginLoading(false);
  }, []);

  const handleLogout = useCallback(() => {
     localStorage.removeItem('authToken');
     setToken(null);
     setUser(null);
     setInstanceConnected(false);
  }, []);

  const handleConnectSuccess = useCallback(() => {
    setInstanceConnected(true);
  }, []);

  const value = {
    token,
    user,
    instanceConnected,
    isLoading: isLoginLoading || isStatusLoading,
    loginError,
    handleLogin,
    handleLogout,
    handleConnectSuccess,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
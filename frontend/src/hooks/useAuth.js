import React, { useState, useEffect, useCallback, createContext, useContext } from 'react';
import api from '../services/api';

const AuthContext = createContext(null);

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth deve ser usado dentro de um AuthProvider");
  }
  return context;
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem('authToken'));
  const [user, setUser] = useState(null);
  const [instanceConnected, setInstanceConnected] = useState(false);
  const [isLoginLoading, setIsLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState('');
  const [isStatusLoading, setIsStatusLoading] = useState(true); // Começa carregando

  const isAuthenticated = !!token;

  // Função para buscar dados do usuário
  const fetchUser = useCallback(async () => {
    if (!token) return;
    try {
        const { data } = await api.get('/users/me');
        setUser(data);

        // Se for cliente e tiver instância, checa o status
        if (data.tenant?.type !== 'ADMIN' && data.tenant?.instance_name) {
             await checkInstanceStatus(data.tenant.instance_name);
        } else {
             // Admin ou sem instância não precisa de conexão "open"
             setInstanceConnected(false);
        }
    } catch (error) {
        console.error("Erro ao buscar usuário:", error);
        if (error.response?.status === 401) handleLogout();
    } finally {
        setIsStatusLoading(false);
    }
  }, [token]);

  // Verifica status da instância (Blindado)
  const checkInstanceStatus = async (instanceName) => {
      if (!instanceName) return;
      try {
          const { data } = await api.get('/evolution/instance/status');

          // Suporta diferentes formatos de retorno da Evolution
          const state = data.instance?.state || data.state;

          // ACEITA 'open' OU 'connecting' para não chutar o usuário durante reconexões
          if (state === 'open' || state === 'connecting') {
            setInstanceConnected(true);
          } else {
            console.warn("Instância desconectada. Estado:", state);
            setInstanceConnected(false);
          }
      } catch (err) {
          console.error("Erro ao verificar status (mantendo estado anterior):", err);
          // Não desconecta em caso de erro de rede temporário, assume que está ok se já estava
          // Isso evita o "pisca" de tela
      }
  };

  // Inicialização
  useEffect(() => {
    const initAuth = async () => {
      setIsStatusLoading(true);
      if (token) {
        await fetchUser();
      } else {
        setIsStatusLoading(false);
      }
    };
    initAuth();
  }, [token, fetchUser]);

  const handleLogin = useCallback(async (username, password) => {
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
        setIsLoginLoading(false);
        return true;
      } else {
        throw new Error("Resposta de login inválida.");
      }
    } catch (err) {
      setLoginError('Usuário ou senha inválidos.');
      setIsLoginLoading(false);
      return false;
    }
  }, []);

  const handleLogout = useCallback(() => {
     localStorage.removeItem('authToken');
     setToken(null);
     setUser(null);
     setInstanceConnected(false);
  }, []);

  // Força o estado para True manualmente (usado pelo botão "Voltar ao Chat")
  const handleConnectSuccess = useCallback(() => {
    setInstanceConnected(true);
    // Opcional: refazer o fetchUser para garantir
  }, []);

  const value = {
    token,
    user,
    isAuthenticated,
    instanceConnected,
    isLoading: isLoginLoading || isStatusLoading, // Combina os loadings
    loginError,
    handleLogin,
    handleLogout,
    handleConnectSuccess,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
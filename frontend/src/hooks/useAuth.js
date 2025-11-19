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
  const [isStatusLoading, setIsStatusLoading] = useState(true);

  const isAuthenticated = !!token;

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
          handleLogout();
        } finally {
          setIsStatusLoading(false);
        }
      } else {
        setIsStatusLoading(false);
      }
    };
    checkInstanceStatus();
  }, [token]);

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

  const handleConnectSuccess = useCallback(() => {
    setInstanceConnected(true);
  }, []);

  // ✨ CERTIFIQUE-SE QUE handleConnectSuccess ESTÁ AQUI
  const value = {
    token,
    user,
    isAuthenticated,
    instanceConnected,
    isLoading: isLoginLoading || isStatusLoading,
    loginError,
    handleLogin,
    handleLogout,
    handleConnectSuccess, // <--- AQUI
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
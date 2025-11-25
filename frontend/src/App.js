import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';

// Componentes de Página
import Login from './components/Login';
import MainLayout from './components/MainLayout';
import ManagementPage from './pages/ManagementPage';
import AdminPage from './pages/AdminPage';
import LandingPage from './pages/LandingPage';

// Contexto
import { useAuth } from './hooks/useAuth';
import { ChatProvider } from './context/ChatContext';
import { ToastProvider } from './context/ToastContext';

// --- TELA DE LOADING ---
const ConnectionLoadingScreen = ({ onAnimationEnd }) => {
  const [loadingTextIndex, setLoadingTextIndex] = useState(0);
  const [isFadingOut, setIsFadingOut] = useState(false);
  const messages = ["Acessando o Cosmos...", "Sincronizando Neurônios...", "Carregando Interface...", "Bem-vindo ao Futuro..."];

  useEffect(() => {
    const textInterval = setInterval(() => setLoadingTextIndex(p => (p + 1) % messages.length), 2000);
    const fadeOutTimeout = setTimeout(() => setIsFadingOut(true), 3500);
    return () => { clearInterval(textInterval); clearTimeout(fadeOutTimeout); };
  }, []);

  const handleAnimationEnd = (e) => {
    if (e.animationName.includes('fadeOut') || isFadingOut) onAnimationEnd();
  };

  return (
    <div className={`connection-loading-screen ${isFadingOut ? 'fade-out' : ''}`} onAnimationEnd={handleAnimationEnd}>
      {/* Mantenha seu SVG do logo e estrutura aqui */}
      <div className="loading-text">Carregando...</div>
    </div>
  );
};

// --- ROTA INTELIGENTE (ROOT) ---
// ✨ AQUI ESTÁ A MÁGICA: Decide se mostra Landing ou App
const RootRoute = () => {
  const { isAuthenticated, user, instanceConnected, isLoading } = useAuth();

  if (isLoading) return <div style={{ height: '100vh', background: '#020617' }}></div>;

  // 1. Se NÃO estiver logado, mostra a Landing Page (Venda)
  if (!isAuthenticated) {
    return <LandingPage />;
  }

  // 2. Se estiver logado, redireciona para o lugar certo
  if (user?.tenant?.type === 'ADMIN' || user?.tenant_id === 'admin_master') {
    return <Navigate to="/admin" replace />;
  }

  // 3. Se for usuário normal conectado, vai pro Chat
  if (instanceConnected) {
    return <Navigate to="/app" replace />;
  }

  // 4. Se for usuário normal desconectado, vai pro Manager
  return <Navigate to="/manager" replace />;
};


// --- ROTAS DE PROTEÇÃO ---
const PrivateRoute = ({ children }) => {
  const { isAuthenticated, token, isLoading } = useAuth();
  if (isLoading) return <div></div>;
  if (!isAuthenticated || !token) return <Navigate to="/login" />;
  return children;
};

const PrivateSystemRoute = ({ children }) => {
  const { isAuthenticated, instanceConnected, user, isLoading } = useAuth();
  if (isLoading) return <div></div>;
  if (!isAuthenticated || !user) return <Navigate to="/login" />;
  if (user?.tenant?.type === 'ADMIN') return <Navigate to="/admin" />;
  if (!instanceConnected) return <Navigate to="/manager" />;
  return children;
};

// --- APP PRINCIPAL ---
function App() {
  const { isAuthenticated, handleLogout } = useAuth();
  const [showTransitionScreen, setShowTransitionScreen] = useState(false);
  const [hasPlayedIntro, setHasPlayedIntro] = useState(false);

  useEffect(() => {
    if (isAuthenticated && !showTransitionScreen && !hasPlayedIntro) {
      setShowTransitionScreen(true);
      setHasPlayedIntro(true);
    }
  }, [isAuthenticated, showTransitionScreen, hasPlayedIntro]);

  return (
    <ToastProvider>
      <Router>
        <div className="App">
          {showTransitionScreen ? (
            <ConnectionLoadingScreen onAnimationEnd={() => setShowTransitionScreen(false)} />
          ) : (
            <Routes>
              {/* ✨ ROTA RAIZ AGORA É INTELIGENTE */}
              <Route path="/" element={<RootRoute />} />

              <Route path="/login" element={!isAuthenticated ? <Login /> : <Navigate to="/" />} />

              <Route path="/admin" element={<PrivateRoute><AdminPage /></PrivateRoute>} />

              <Route path="/manager" element={<PrivateRoute><ManagementPage /></PrivateRoute>} />

              <Route path="/app" element={
                <PrivateSystemRoute>
                  <ChatProvider>
                    <MainLayout onLogout={handleLogout} />
                  </ChatProvider>
                </PrivateSystemRoute>
              } />

              <Route path="*" element={<Navigate to="/" />} />
            </Routes>
          )}
        </div>
      </Router>
    </ToastProvider>
  );
}

export default App;
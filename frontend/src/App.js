import React, { useState, useEffect, useCallback } from 'react';
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import Drawer from 'react-modern-drawer';
import 'react-modern-drawer/dist/index.css';

import Login from './components/Login';
import ConversationList from './components/ConversationList';
import ChatPanel from './components/ChatPanel';
import CopilotPanel from './components/CopilotPanel';
import NewConversationModal from './components/NewConversationModal';
import ConnectInstancePage from './components/ConnectInstancePage';

import { useAuth } from './hooks/useAuth';
import { useResponsive } from './hooks/useResponsive';
import { ChatProvider, useChat } from './context/ChatContext';

const CosmosLogo = () => (
  <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2a3 3 0 0 0-3 3v1a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 11h-2"/><path d="M5 11H3"/><path d="M12 18a3 3 0 0 0 3 3h1a3 3 0 0 0 3-3v-1a3 3 0 0 0-3-3h-1v4Z"/><path d="M12 18a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3v-1a3 3 0 0 1 3-3h1v4Z"/><path d="M12 8v4"/>
  </svg>
);

// --- Tela de Carregamento ---
function ConnectionLoadingScreen({ onAnimationEnd }) {
  const [loadingTextIndex, setLoadingTextIndex] = useState(0);
  const [isFadingOut, setIsFadingOut] = useState(false);
  const messages = ["Acessando o Cosmos...", "Estabelecendo conexão neural...", "Sincronizando com a IA central...", "Preparando sua experiência...", "Quase lá!"];

  useEffect(() => {
    const textInterval = setInterval(() => setLoadingTextIndex(p => (p + 1) % messages.length), 2000);
    // Reduzi um pouco o timeout para ser mais ágil
    const fadeOutTimeout = setTimeout(() => setIsFadingOut(true), 4000);
    return () => { clearInterval(textInterval); clearTimeout(fadeOutTimeout); };
  }, []); // Removido messages.length da dependência para evitar recriação desnecessária

  const handleAnimationEnd = (e) => {
    // Garante que só dispara se for a animação de fade-out
    if (e.animationName.includes('fadeOut') || isFadingOut) {
        onAnimationEnd();
    }
  };

  return (
    <div className={`connection-loading-screen ${isFadingOut ? 'fade-out' : ''}`} onAnimationEnd={handleAnimationEnd}>
      <div className="connection-logo"><CosmosLogo /></div>
      <div className="loading-text" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px' }}>
        <div className="spinner-dot"></div> {messages[loadingTextIndex]}
      </div>
      <div className="animated-background-lines"><div className="line"></div><div className="line"></div><div className="line"></div><div className="line"></div><div className="line"></div></div>
    </div>
  );
}

// --- MainLayout ---
const MainLayout = ({ onLogout }) => {
  const isMobile = useResponsive();
  const { isCopilotOpen, handleToggleCopilot, handleBackToList, activeConversationId, setIsCopilotOpen } = useChat();

  const { isModalOpen, handleCloseModal, handleStartConversation } = useChat();
  const [isModalLoading, setIsModalLoading] = useState(false);

  const onStart = async (number, message) => {
    setIsModalLoading(true);
    const success = await handleStartConversation(number, message);
    if (success) handleCloseModal();
    setIsModalLoading(false);
  };

  useEffect(() => { if (!isMobile) setIsCopilotOpen(true); }, [isMobile, setIsCopilotOpen]);
  useEffect(() => {
    const handleKeyDown = (e) => { if (e.key === 'Escape') handleBackToList(); };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleBackToList]);

  const showCopilot = isCopilotOpen && activeConversationId;

  const layout = isMobile ? (
    <div className="mobile-layout">
      {activeConversationId ? (
        <ChatPanel onToggleCopilot={handleToggleCopilot} onBack={handleBackToList} />
      ) : (
        <ConversationList onLogout={onLogout} />
      )}
      <Drawer open={isCopilotOpen} onClose={handleToggleCopilot} direction='right' size={'80vw'} className='copilot-drawer'>
          <CopilotPanel />
      </Drawer>
    </div>
  ) : (
    <PanelGroup direction="horizontal" className="main-layout desktop-layout">
      <Panel id="sidebar" defaultSize={25} minSize={20} maxSize={30} order={1}>
        <ConversationList onLogout={onLogout} />
      </Panel>
      <PanelResizeHandle />
      <Panel
        id="chat"
        order={2}
        minSize={30}
        defaultSize={showCopilot ? 45 : 75}
        key={showCopilot ? 'chat-compact' : 'chat-full'}
      >
        <ChatPanel onToggleCopilot={handleToggleCopilot} />
      </Panel>
      {showCopilot && (
        <>
          <PanelResizeHandle />
          <Panel id="copilot" defaultSize={30} minSize={20} maxSize={40} order={3}>
            <CopilotPanel />
          </Panel>
        </>
      )}
    </PanelGroup>
  );

  return (
    <>
      {layout}
      <NewConversationModal
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        onStartConversation={onStart}
        isLoading={isModalLoading}
      />
    </>
  );
}

// --- App Component ---
function App() {
  const { isAuthenticated, instanceConnected, token, handleLogout, handleConnectSuccess } = useAuth();
  const [showTransitionScreen, setShowTransitionScreen] = useState(false);
  // ✨ CORREÇÃO: Estado para garantir que a intro rode apenas uma vez
  const [hasPlayedIntro, setHasPlayedIntro] = useState(false);

  const renderContent = () => {
    if (isAuthenticated) {
      if (!instanceConnected && token) {
        return <ConnectInstancePage onConnectSuccess={handleConnectSuccess} />;
      } else if (instanceConnected && token) {
        return (
          <ChatProvider>
            <MainLayout onLogout={handleLogout} />
          </ChatProvider>
        );
      }
    }
    return <Login />;
  };

  useEffect(() => {
    // ✨ CORREÇÃO: Adicionado !hasPlayedIntro na verificação
    // Se estamos logados, mas a intro ainda não tocou, toque-a.
    if (isAuthenticated && token && !showTransitionScreen && !hasPlayedIntro) {
        setShowTransitionScreen(true);
        setHasPlayedIntro(true); // Marca como tocada para não repetir
    }
  }, [isAuthenticated, token, showTransitionScreen, hasPlayedIntro]);

  const handleTransitionEnd = useCallback(() => {
    setShowTransitionScreen(false);
  }, []);

  return (
    <div className="App">
      {showTransitionScreen ? (
          <ConnectionLoadingScreen onAnimationEnd={handleTransitionEnd} />
      ) : (
          renderContent()
      )}
    </div>
  );
}

export default App;
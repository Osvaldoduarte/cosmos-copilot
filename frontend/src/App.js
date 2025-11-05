// Em frontend/src/App.js
// (SUBSTITUA o conteúdo deste arquivo)

import React, { useState } from 'react';
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import Drawer from 'react-modern-drawer';
import 'react-modern-drawer/dist/index.css';
// 💡 REMOVIDO: import { DragDropContext } from 'react-beautiful-dnd';

import Login from './components/Login';
import ConversationList from './components/ConversationList';
import ChatPanel from './components/ChatPanel';
import CopilotPanel from './components/CopilotPanel';
import NewConversationModal from './components/NewConversationModal';
import ConnectInstancePage from './components/ConnectInstancePage';

import { useAuth } from './hooks/useAuth';
import { useResponsive } from './hooks/useResponsive';
import { ChatProvider, useChat } from './context/ChatContext';

// --- Componente 'Main' (lê o contexto) ---
const MainLayout = ({ onLogout }) => {
  const isMobile = useResponsive();

  const {
    isCopilotOpen,
    handleToggleCopilot,
    handleBackToList,
    activeConversationId,
  } = useChat();

  // 💡 REMOVIDO: Handler 'onDragEnd'

  const layout = isMobile ? (
    // --- LAYOUT MOBILE ---
    <div className="mobile-layout">
      {activeConversationId ? (
        <ChatPanel
          onToggleCopilot={handleToggleCopilot}
          onBack={handleBackToList}
        />
      ) : (
        <ConversationList onLogout={onLogout} />
      )}
      <Drawer
          open={isCopilotOpen}
          onClose={handleToggleCopilot}
          direction='right'
          size={'80vw'}
          className='copilot-drawer'
      >
          <CopilotPanel />
      </Drawer>
    </div>
  ) : (
    // --- LAYOUT DESKTOP ---
    <PanelGroup direction="horizontal" className="main-layout">
      <Panel id="sidebar" defaultSize={25} minSize={20} maxSize={35}>
        <ConversationList onLogout={onLogout} />
      </Panel>
      <PanelResizeHandle />
      <Panel id="chat" minSize={30}>
        <ChatPanel onToggleCopilot={handleToggleCopilot} />
      </Panel>
      {isCopilotOpen && (
        <>
          <PanelResizeHandle />
          <Panel id="copilot" defaultSize={30} minSize={20} maxSize={40}>
            <CopilotPanel />
          </Panel>
        </>
      )}
    </PanelGroup>
  );

  // 💡 Retorna o layout SEM o DragDropContext
  return layout;
}


// --- Componente Modal (lê o contexto) ---
const NewConversationModalGlobal = () => {
  const {
    isModalOpen,
    handleCloseModal,
    handleStartConversation,
  } = useChat();
  const [isLoading, setIsLoading] = useState(false);

  const onStart = async (number, message) => {
    setIsLoading(true);
    const success = await handleStartConversation(number, message);
    if (success) {
      handleCloseModal();
    }
    setIsLoading(false);
  };

  return (
    <NewConversationModal
      isOpen={isModalOpen}
      onClose={handleCloseModal}
      onStartConversation={onStart}
      isLoading={isLoading}
    />
  );
};


// --- Função Principal do App (Roteador de Autenticação) ---
function App() {
  const {
    token,
    instanceConnected,
    isLoading: isAuthLoading,
    loginError,
    handleLogin,
    handleLogout,
    handleConnectSuccess,
  } = useAuth();

  if (isAuthLoading) {
    return <div className="loading-screen">Carregando autenticação...</div>;
  }
  if (!token) {
    return <Login onLogin={handleLogin} error={loginError} isLoading={isAuthLoading} />;
  }
  if (token && !instanceConnected) {
    return <ConnectInstancePage onConnectSuccess={handleConnectSuccess} />;
  }

  // App Logado
  return (
    <ChatProvider>
      <div className="app-container">
        <MainLayout onLogout={handleLogout} />
        <NewConversationModalGlobal />
      </div>
    </ChatProvider>
  );
}

export default App;
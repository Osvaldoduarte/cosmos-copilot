// Em frontend/src/context/ChatContext.js
import React, { createContext, useContext } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useChatData } from '../hooks/useChatData';
import { useChatUI } from '../hooks/useChatUI';
import { useChatCopilot } from '../hooks/useChatCopilot';

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  const { token, instanceConnected } = useAuth();

  // 1. Dados (agora retorna updateCopilotState)
  const dataState = useChatData(token, instanceConnected);

  // 2. UI
  const uiState = useChatUI(dataState.setActiveConversationId);

  // 3. Copilot
  // Passamos dataState.conversations para leitura
  // E dataState.updateCopilotState para escrita
  const copilotState = useChatCopilot(
    dataState.conversations,
    dataState.activeConversationId,
    uiState.setIsCopilotOpen,
    dataState.updateCopilotState // <--- CONEXÃO AQUI
  );

  const combinedState = {
    ...dataState,
    ...uiState,
    ...copilotState,
  };

  return (
    <ChatContext.Provider value={combinedState}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const context = useContext(ChatContext);
  if (context === null) {
    throw new Error("useChat deve ser usado dentro de um ChatProvider");
  }
  return context;
}
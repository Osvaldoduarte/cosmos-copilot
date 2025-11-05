// Em frontend/src/context/ChatContext.js
// (SUBSTITUA o conteúdo deste arquivo)

import React, { createContext, useContext } from 'react';
import { useAuth } from '../hooks/useAuth';

// 1. Importa os 3 novos hooks
import { useChatData } from '../hooks/useChatData';
import { useChatUI } from '../hooks/useChatUI';
import { useChatCopilot } from '../hooks/useChatCopilot';

// 2. Deleta a importação antiga
// import { useChatManager } from '../hooks/useChatManager';

// 1. Criar o Contexto
const ChatContext = createContext(null);

// 2. Criar o Provedor (Provider)
export function ChatProvider({ children }) {
  const { token, instanceConnected } = useAuth();

  // 3. Chama os 3 hooks
  const dataState = useChatData(token, instanceConnected);
  const uiState = useChatUI(dataState.setActiveConversationId);
  const copilotState = useChatCopilot(
    dataState.conversations,
    dataState.activeConversationId
  );

  // 4. Combina tudo
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

// 3. Criar o Hook de Consumidor
export function useChat() {
  const context = useContext(ChatContext);
  if (context === null) {
    throw new Error("useChat deve ser usado dentro de um ChatProvider");
  }
  return context;
}
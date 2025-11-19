// Em frontend/src/hooks/useChatUI.js
import { useState, useCallback } from 'react';
import { useResponsive } from './useResponsive';

export function useChatUI(setActiveConversationId) {
  const isMobile = useResponsive();

  const [isModalOpen, setIsModalOpen] = useState(false);
  // O Copilot abre por padrão se não for mobile
  const [isCopilotOpen, setIsCopilotOpen] = useState(!isMobile);

  const handleCloseModal = useCallback(() => setIsModalOpen(false), []);
  const handleNewConversationClick = useCallback(() => setIsModalOpen(true), []);
  const handleToggleCopilot = useCallback(() => setIsCopilotOpen(prev => !prev), []);

  const handleBackToList = useCallback(() => {
    setActiveConversationId(null);
  }, [setActiveConversationId]);

  return {
    isModalOpen,
    isCopilotOpen,
    setIsCopilotOpen, // <--- 💡 ADICIONADO: Exporta a função para ser usada no Copilot
    isMobile,
    handleCloseModal,
    handleNewConversationClick,
    handleToggleCopilot,
    handleBackToList,
  };
}
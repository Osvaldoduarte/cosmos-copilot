// Em frontend/src/hooks/useChatUI.js
// (SUBSTITUA o conteúdo deste arquivo)

import { useState, useCallback } from 'react';
import { useResponsive } from './useResponsive'; // 💡 Importa o hook de responsividade

/**
 * Hook (Refatorado v2)
 * Responsabilidade Única: Gerenciar o estado da UI.
 * 💡 CORRIGE O BUG do Copilot "sumido".
 */
export function useChatUI(setActiveConversationId) {
  const isMobile = useResponsive();

  const [isModalOpen, setIsModalOpen] = useState(false);
  // 💡 CORREÇÃO: O Copilot é aberto por padrão se NÃO for mobile
  const [isCopilotOpen, setIsCopilotOpen] = useState(!isMobile);

  // Handlers de UI (com useCallback)
  const handleCloseModal = useCallback(() => setIsModalOpen(false), []);
  const handleNewConversationClick = useCallback(() => setIsModalOpen(true), []);

  // 💡 O Toggle agora é a única fonte de verdade
  const handleToggleCopilot = useCallback(() => setIsCopilotOpen(prev => !prev), []);

  const handleBackToList = useCallback(() => {
    setActiveConversationId(null);
  }, [setActiveConversationId]);

  return {
    isModalOpen,
    isCopilotOpen,
    isMobile, // 💡 Exporta o estado 'isMobile'
    handleCloseModal,
    handleNewConversationClick,
    handleToggleCopilot,
    handleBackToList,
  };
}
// frontend/src/components/DragDropZone.js
import React from 'react';
import { useChat } from '../context/ChatContext';
import '../styles/drag-drop-zone.css';

const DragDropZone = () => {
    const {
        isDragging,
        draggedMessage,
        isCopilotOpen,
        handleSuggestionRequest,
        handleToggleCopilot,
        activeConversationId
    } = useChat();

    // Só mostra se estiver arrastando E Copilot fechado
    if (!isDragging || isCopilotOpen) return null;

    const handleDragOver = (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
    };

    const handleDrop = async (e) => {
        e.preventDefault();

        const messageText = e.dataTransfer.getData('text/plain');
        if (messageText && activeConversationId) {
            // 1. Abre o Copilot
            handleToggleCopilot();

            // 2. Aguarda um frame para o Copilot abrir
            requestAnimationFrame(() => {
                // 3. Envia para análise
                handleSuggestionRequest(messageText, activeConversationId);
            });
        }
    };

    return (
        <div
            className="drag-drop-zone"
            onDragOver={handleDragOver}
            onDrop={handleDrop}
        >
            <div className="drop-zone-content">
                <div className="drop-zone-icon">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
                        <path d="M12 3l1.912 5.813a2 2 0 0 0 1.272 1.272L21 12l-5.813 1.912a2 2 0 0 0 -1.272 1.272L12 21l-1.912-5.813a2 2 0 0 0 -1.272-1.272L3 12l5.813-1.912a2 2 0 0 0 1.272-1.272L12 3z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                </div>
                <div className="drop-zone-text">
                    <h3>Solte aqui para analisar</h3>
                    <p>O Copilot será aberto automaticamente</p>
                </div>
                {draggedMessage && (
                    <div className="drop-zone-preview">
                        <span>{draggedMessage.content.substring(0, 50)}...</span>
                    </div>
                )}
            </div>
        </div>
    );
};

export default DragDropZone;

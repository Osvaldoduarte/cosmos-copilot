// frontend/src/components/MessageContextMenu.js
import React from 'react';

// O menu agora recebe as coordenadas x e y da tela do evento.
function MessageContextMenu({ x, y, onAnalyze, onClose }) {

  const handleAnalyze = (e) => {
      e.stopPropagation();
      onAnalyze();
      onClose(); // Fecha após a ação
  };

  // O menu em si
  const menu = (
    <div
      className="message-context-menu"
      // Usa as coordenadas de página (x e y) fornecidas pelo ChatPanel
      style={{ top: `${y}px`, left: `${x}px` }}
      onClick={(e) => e.stopPropagation()} // Impede que o clique no menu feche o próprio menu
    >
      <button onClick={handleAnalyze}>Enviar ao Copilot</button>
    </div>
  );

  // O overlay de fundo que, ao ser clicado, fecha o menu
  return (
    // O onClick no overlay agora fecha o menu
    <div className="context-menu-overlay" onClick={onClose}>
      {menu}
    </div>
  );
}

export default MessageContextMenu;
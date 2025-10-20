import React from 'react';

function MessageContextMenu({ x, y, onAnalyze, onClose }) {
  // O menu em si
  const menu = (
    <div
      className="message-context-menu"
      style={{ top: `${y}px`, left: `${x}px` }}
      onClick={(e) => e.stopPropagation()} // Impede que o clique no menu feche o próprio menu
    >
      <button onClick={onAnalyze}>Enviar ao Copilot</button>
    </div>
  );

  // O overlay de fundo que, ao ser clicado, fecha o menu
  return (
    <div className="context-menu-overlay" onClick={onClose}>
      {menu}
    </div>
  );
}

export default MessageContextMenu;
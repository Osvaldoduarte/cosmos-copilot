// frontend/src/components/Lightbox.js
import React, { useEffect } from 'react';

const CloseIcon = () => (<svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>);

/**
 * Componente Lightbox para visualização de imagem em tela cheia.
 * Depende das classes CSS .lightbox-overlay, .lightbox-content, .lightbox-close-btn
 *
 * @param {{ imageUrl: string, onClose: function }} props
 */
function Lightbox({ imageUrl, onClose }) {

  // Efeito para fechar ao pressionar ESC
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  if (!imageUrl) {
    return null;
  }

  return (
    <div className="lightbox-overlay" onClick={onClose}>
      <div className="lightbox-content" onClick={(e) => e.stopPropagation()}>
        <img src={imageUrl} alt="Visualização em Tela Cheia" />
        <button className="lightbox-close-btn" onClick={onClose}>
          <CloseIcon />
        </button>
      </div>
    </div>
  );
}

export default Lightbox;
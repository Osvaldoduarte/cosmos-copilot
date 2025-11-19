// frontend/src/components/VideoSuggestionCard.js
import React from 'react';

// O componente agora usa as classes do tema Glassmorphism
const VideoSuggestionCard = ({ video }) => {
  // Ajustamos a desestruturação para lidar com o mock (video.url vs video.video_url)
  const videoUrl = video?.url || video?.video_url;
  if (!video || !videoUrl) {
    return null;
  }

  const isYouTube = videoUrl.includes('youtube.com') || videoUrl.includes('youtu.be');

  return (
    // Usa a classe genérica 'glass-card' e um estilo adicional para diferenciá-lo
    <div className="glass-card video-card" style={{ marginBottom: '20px', borderLeft: '3px solid #4ec9b0' }}>
      <div className="card-header">
        <h4 style={{ color: '#4ec9b0' }}>📹 Sugestão de Conteúdo</h4>
      </div>
      <p className="card-content" style={{ fontSize: '0.95rem', color: '#ccc' }}>
        Encontramos um vídeo em sua base de conhecimento que pode complementar a resposta.
      </p>
      <a
        href={videoUrl}
        target="_blank"
        rel="noopener noreferrer"
        // Usamos um botão de estilo simples para o link
        className="clear-btn"
        style={{ color: '#00aaff', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '5px' }}
      >
        {isYouTube ? 'Assistir no YouTube' : 'Abrir Vídeo'}
      </a>
    </div>
  );
};

export default VideoSuggestionCard;
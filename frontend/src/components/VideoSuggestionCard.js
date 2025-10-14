import React from 'react';

// Você pode precisar ajustar os estilos (className, etc.) para combinar com seu projeto.
const cardStyle = {
  border: '1px solid #ddd',
  borderRadius: '8px',
  padding: '16px',
  marginTop: '16px',
  backgroundColor: '#f9f9f9',
};

const linkStyle = {
  color: '#007bff',
  textDecoration: 'none',
  fontWeight: 'bold',
};

/**
 * Um componente que mostra um link para um vídeo de sugestão.
 * Ele só é renderizado se receber uma prop 'video' válida com uma propriedade 'video_url'.
 * @param {{ video: { video_url: string } }} props
 */
const VideoSuggestionCard = ({ video }) => {
  if (!video || !video.video_url) {
    return null;
  }

  const isYouTube = video.url.includes('youtube.com') || video.url.includes('youtu.be');

  return (
    <div className="video-card mb-6 p-4 bg-gray-50 border border-gray-200 rounded-lg shadow-sm">
      <h4 className="text-md font-semibold mb-2 text-gray-700">📹 Sugestão de Vídeo: {video.title}</h4>
      <p className="text-sm text-gray-600 mb-3">
        Encontramos um conteúdo na base de conhecimento que pode complementar a resposta.
      </p>
      <a
        href={video.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-sm font-bold text-blue-600 hover:underline"
      >
        {isYouTube ? 'Assistir no YouTube' : 'Abrir Vídeo'}
      </a>
    </div>
  );
};

export default VideoSuggestionCard;
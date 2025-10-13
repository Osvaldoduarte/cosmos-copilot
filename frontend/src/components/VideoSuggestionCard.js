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

  // ==================================================================
  // A CORREÇÃO ESTÁ AQUI
  // ==================================================================
  //
  // Esta verificação é a "guarda".
  // Se a prop 'video' não existir, OU se ela não tiver a chave 'video_url',
  // o componente retorna 'null', ou seja, ele não renderiza NADA na tela e para a execução.
  if (!video || !video.video_url) {
    return null;
  }

  // Se o código chegou até este ponto, temos 100% de certeza
  // de que 'video' é um objeto e 'video.video_url' existe e é uma string.
  // Agora podemos usar a função .includes() com segurança.
  const isYouTube = video.video_url.includes('youtube.com');

  return (
    <div style={cardStyle}>
      <h4>📹 Vídeo de Treinamento Sugerido</h4>
      <p>
        Encontrei um vídeo que pode te ajudar com isso.
      </p>
      <a
        href={video.video_url}
        target="_blank"
        rel="noopener noreferrer"
        style={linkStyle}
      >
        {isYouTube ? 'Assistir no YouTube' : 'Abrir vídeo'}
      </a>
    </div>
  );
};

export default VideoSuggestionCard;
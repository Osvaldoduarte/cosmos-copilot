// Arquivo: frontend/src/components/CopilotPanel.js (Versão Final e Completa)

import React, { useState, useEffect } from 'react';
import VideoSuggestionCard from './VideoSuggestionCard';

// --- ÍCONES ---
const SpinnerIcon = () => ( <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 4.75V6.25" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"></path><path d="M17.125 6.875L16.065 7.935" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"></path><path d="M19.25 12L17.75 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"></path><path d="M17.125 17.125L16.065 16.065" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"></path><path d="M12 17.75V19.25" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"></path><path d="M6.875 17.125L7.935 16.065" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"></path><path d="M4.75 12L6.25 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"></path><path d="M6.875 6.875L7.935 7.935" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"></path></svg> );
const DragDropIcon = () => ( <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M12 16.5V3M12 3L15.5 6.5M12 3L8.5 6.5M4 13.5V20C4 20.5523 4.44772 21 5 21H19C19.5523 21 20 20.5523 20 20V13.5" stroke="var(--text-secondary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg> );
const CloseIcon = () => ( <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M18 6L6 18M6 6L18 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg> );

// --- SUB-COMPONENTES ---

// Componente para renderizar o texto das sugestões
const TonalSuggestionCard = ({ title, options, onUseSuggestion, is_private, onDelete }) => {
  const [activeText, setActiveText] = useState('');
  useEffect(() => {
    if (options && options.length > 0) {
      const recommendedOption = options.find(opt => opt.is_recommended) || options[0];
      setActiveText(recommendedOption.text);
    }
  }, [options]);

  if (!options || !options[0] || !options[0].text) return null;

  return (
    <div className="response-card suggestion-card">
      <div className="card-header">
        <h3>{title}</h3>
        {is_private ? (
          <button className="suggestion-delete-btn" onClick={onDelete}><CloseIcon /></button>
        ) : (
          <button className="use-suggestion-btn" onClick={() => onUseSuggestion(activeText)}>Usar esta resposta</button>
        )}
      </div>
      <p style={{ whiteSpace: 'pre-wrap' }}>{activeText}</p>
    </div>
  );
};

// Componente para a área de interação inferior (input + drag-drop)
const InteractionArea = ({ onQuerySubmit, compact }) => {
    const [query, setQuery] = useState('');
    const handleSubmit = (e) => { e.preventDefault(); if (!query.trim()) return; onQuerySubmit(query); setQuery(''); };
    const containerClass = compact ? "interaction-area compact" : "interaction-area";
    return (
        <div className={containerClass}>
            <form onSubmit={handleSubmit} className="private-query-form">
                <input type="text" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Pergunte algo para a IA..." />
                <button type="submit">Analisar</button>
            </form>
            <div className="drag-drop-prompt"><DragDropIcon /><p>Ou arraste uma mensagem do cliente aqui.</p></div>
        </div>
    );
};

// Componente de Animação de Carregamento
const LoadingAnimation = () => {
  const loadingTexts = [ "Analisando histórico...", "Consultando base de conhecimento...", "Avaliando estratégia...", "Formulando sugestões..." ];
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentIndex((prevIndex) => (prevIndex + 1) % loadingTexts.length);
    }, 2000);
    return () => clearInterval(interval);
  }, [loadingTexts.length]);

  return (
    <div className="loading-animation-card">
      <div className="loading-spinner-icon">
        <SpinnerIcon />
      </div>
      <p key={currentIndex} className="fade-in-text">{loadingTexts[currentIndex]}</p>
    </div>
  );
};


// --- COMPONENTE PRINCIPAL ---
// Arquivo: frontend/src/components/CopilotPanel.js (versão reordenada)

function CopilotPanel({ isLoading, error, suggestions, onUseSuggestion, onDeleteSuggestion, onMessageDrop, onClearSuggestions, onPrivateQuerySubmit }) {
  const handleDragOver = (e) => e.preventDefault();

  const handleDrop = (e) => {
    e.preventDefault();
    const queryText = e.dataTransfer.getData("text/plain");
    if (queryText) onMessageDrop(queryText);
  };

  const isCompact = suggestions.length > 0 || isLoading;

  return (
    <div className="copilot-panel" onDragOver={handleDragOver} onDrop={handleDrop}>
      <div className="copilot-header">
        {suggestions.length > 0 && !isLoading && (
          <button className="clear-suggestions-btn" onClick={onClearSuggestions}><CloseIcon /> Limpar sugestões</button>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="copilot-content-wrapper">
        <div className="interaction-area-container">
          <InteractionArea
            onQuerySubmit={onPrivateQuerySubmit}
            compact={isCompact}
          />
        </div>

        {isLoading && <LoadingAnimation />}

{suggestions.length > 0 && (
          <div className="copilot-output">
            {suggestions.map(item => {
              // AQUI ESTÁ A LÓGICA DE DECISÃO
              if (item.is_private) {
                // SE FOR UMA CONSULTA PRIVADA, RENDERIZA O CARD SIMPLES
                return (
                  <div key={item.id} className="suggestion-group">
                    {/* O card agora contém tanto a pergunta quanto a resposta */}
                    <div className="response-card suggestion-card suggestion-card-private">

                      {/* A pergunta agora é o cabeçalho do card */}
                      <div className="card-header private-header">
                        <h3>Sua pergunta: "{item.private_query}"</h3>
                        <button className="suggestion-delete-btn" onClick={() => onDeleteSuggestion(item.id)}>
                          <CloseIcon />
                        </button>
                      </div>

                      {/* A resposta da IA */}
                      {item.immediate_answer && (
                        <p>{item.immediate_answer}</p>
                      )}
                    </div>
                  </div>
                );
              } else {
                // SE FOR UMA SUGESTÃO PARA O CLIENTE, RENDERIZA O LAYOUT COMPLETO
                return (
                  <div key={item.id} className="suggestion-group">
                    {item.query && ( <blockquote className="suggestion-query">Referente a: "{item.query}"</blockquote> )}

                    {/* Card de Resposta Imediata (para o cliente) */}
                    {item.immediate_answer && (
                      <div className="response-card suggestion-card">
                        <div className="card-header">
                          <h3>💡 Sugestão de Resposta</h3>
                          <button className="use-suggestion-btn" onClick={() => onUseSuggestion(item.id, item.immediate_answer, 'immediate_answer')}>
                            Usar
                          </button>
                        </div>
                        <p>{item.immediate_answer}</p>
                      </div>
                    )}

                    {/* Card de Próximo Passo (para o cliente) */}
                    {item.follow_up_options && item.follow_up_options.length > 0 && (
                      <div className="response-card suggestion-card" style={{marginTop: '1rem'}}>
                         <div className="card-header">
                          <h3>➡️ Próximo Passo Sugerido</h3>
                          <button className="use-suggestion-btn" onClick={() => onUseSuggestion(item.id, item.follow_up_options[0].text, 'follow_up_options')}>
                            Usar
                          </button>
                        </div>
                        {item.follow_up_options.map((option, index) => (
                          <p key={index}>{option.text}</p>
                        ))}
                      </div>
                    )}

                    {/* Card de Vídeo (se houver) */}
                    {item.video && <VideoSuggestionCard video={item.video} />}
                  </div>
                );
              }
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default CopilotPanel;
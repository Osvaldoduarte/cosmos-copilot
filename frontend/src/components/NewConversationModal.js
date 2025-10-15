import React, { useState, useEffect } from 'react';

function NewConversationModal({ isOpen, onClose, onStartConversation, isLoading }) {
  const [number, setNumber] = useState('');
  const [message, setMessage] = useState('');

  // --- AS LINHAS QUE FALTAVAM ESTÃO AQUI ---
  const [contactPreview, setContactPreview] = useState(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState('');
  // -----------------------------------------

  // Efeito para buscar os dados do contato enquanto o usuário digita
  useEffect(() => {
    // Limpa o preview se o campo de número estiver vazio
    if (!number) {
      setContactPreview(null);
      setPreviewError('');
      return;
    }

    // Formata o número para remover caracteres não numéricos
    const cleanedNumber = number.replace(/\D/g, '');

    // Só busca se o número tiver um tamanho razoável (evita buscas desnecessárias)
    if (cleanedNumber.length >= 11 && cleanedNumber.length <= 13) {
      const timer = setTimeout(() => {
        fetchContactInfo(cleanedNumber);
      }, 800); // Espera 800ms após o usuário parar de digitar para fazer a busca

      // Limpa o timer se o usuário voltar a digitar (otimização)
      return () => clearTimeout(timer);
    }
  }, [number]); // Este efeito roda toda vez que a variável 'number' muda

  // Função que chama o backend para buscar os dados do contato
  const fetchContactInfo = async (num) => {
    setIsPreviewLoading(true);
    setPreviewError('');
    setContactPreview(null);
    try {
      const response = await fetch(`http://127.0.0.1:8000/contacts/info/${num}`);
      if (!response.ok) {
        throw new Error('Contato não encontrado no WhatsApp.');
      }
      const data = await response.json();
      setContactPreview(data);
    } catch (err) {
      setPreviewError(err.message);
    } finally {
      setIsPreviewLoading(false);
    }
  };

  // Função para lidar com o envio do formulário (iniciar a conversa)
  const handleSubmit = (e) => {
    e.preventDefault();
    // Lógica de formatação automática do número (já implementada)
    const cleanedNumber = number.replace(/\D/g, '');
    let finalNumber;
    if (cleanedNumber.length === 13) {
      finalNumber = cleanedNumber;
    } else if (cleanedNumber.length === 11) {
      finalNumber = '55' + cleanedNumber;
    } else if (cleanedNumber.length === 9) {
      finalNumber = '5541' + cleanedNumber;
    } else {
      finalNumber = cleanedNumber.startsWith('55') ? cleanedNumber : '55' + cleanedNumber;
    }
    onStartConversation(finalNumber, message);
  };

  if (!isOpen) {
    return null;
  }

  // Renderização do Modal
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h2>Iniciar Nova Conversa</h2>
        <p>Digite o número do WhatsApp e a primeira mensagem.</p>
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            value={number}
            onChange={(e) => setNumber(e.target.value)}
            placeholder="Ex: 41999998888"
            required
            disabled={isLoading}
          />

          {/* Bloco para mostrar o preview do contato */}
          {isPreviewLoading && <div className="preview-info">Buscando contato...</div>}
          {previewError && <div className="preview-info error">{previewError}</div>}
          {contactPreview && (
            <div className="contact-preview">
              <img src={contactPreview.avatar_url || `https://i.pravatar.cc/150?u=${number}`} alt="Avatar" />
              <span>{contactPreview.name}</span>
            </div>
          )}

          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Sua primeira mensagem..."
            rows="4"
            required
            disabled={isLoading}
          ></textarea>
          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose} disabled={isLoading}>
              Cancelar
            </button>
            <button type="submit" className="btn-primary" disabled={isLoading || !number || !message}>
              {isLoading ? 'Enviando...' : 'Iniciar Conversa'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default NewConversationModal;
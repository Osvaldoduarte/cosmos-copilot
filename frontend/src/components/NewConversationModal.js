import React, { useState } from 'react';
import { useChat } from '../context/ChatContext';
import { useToast } from '../context/ToastContext';
import '../styles/management.css'; // Reutiliza o CSS bonito do manager

const NewConversationModal = ({ onClose }) => {
  const { handleStartConversation } = useChat();
  const notify = useToast();
  const [number, setNumber] = useState('');
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);

    // Limpeza básica do número (remove caracteres não numéricos)
    const cleanNumber = number.replace(/\D/g, '');

    if (cleanNumber.length < 10) {
      notify.warning("Número inválido. Use o formato DDD + Número (ex: 11999999999)");
      setIsLoading(false);
      return;
    }

    const success = await handleStartConversation(cleanNumber, message);
    setIsLoading(false);

    if (success) {
      onClose(); // Fecha o modal se deu certo
    } else {
      notify.error("Erro ao iniciar conversa. Verifique o número.");
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>

        {/* Cabeçalho */}
        <div className="modal-header">
          <h3>Nova Conversa</h3>
          <button onClick={onClose} className="close-btn">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        {/* Formulário */}
        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-group">
            <label>Número do WhatsApp (com DDD)</label>
            <input
              type="text"
              placeholder="Ex: 11999998888"
              value={number}
              onChange={(e) => setNumber(e.target.value)}
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label>Mensagem Inicial</label>
            <input
              type="text"
              placeholder="Ex: Olá, gostaria de falar sobre..."
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              required
            />
          </div>

          <div className="modal-actions">
            <button type="button" onClick={onClose} className="btn btn-secondary">
              Cancelar
            </button>
            <button type="submit" disabled={isLoading} className="btn btn-primary">
              {isLoading ? 'Iniciando...' : 'Iniciar Conversa'}
            </button>
          </div>
        </form>

      </div>
    </div>
  );
};

export default NewConversationModal;
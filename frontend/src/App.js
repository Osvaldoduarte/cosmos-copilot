// Arquivo: frontend/src/App.js (Versão Definitiva com Polling e Evolução API)

import React, { useState, useEffect, useCallback } from 'react'; // Adicionado useEffect e useCallback
import ConversationList from './components/ConversationList';
import ChatPanel from './components/ChatPanel';
import CopilotPanel from './components/CopilotPanel';
// Removida importação de initialData; o backend é a fonte de dados

function App() {
  const [conversations, setConversations] = useState({}); // Iniciado com vazio para receber do backend
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [suggestionsByConvo, setSuggestionsByConvo] = useState({});
  const [stagesByConvo, setStagesByConvo] = useState({});

  // --- FUNÇÃO DE POLLING PARA BUSCAR DADOS DO BACKEND ---
  // Reintroduzida a função de Polling perdida
  const fetchConversations = useCallback(async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/conversations');
      if (!response.ok) {
        throw new Error('Falha ao buscar conversas do backend.');
      }
      const data = await response.json();

      if (data.status === 'success' && data.conversations) {
        const newConversations = {};
        const newSuggestionsByConvo = {};
        const newStagesByConvo = {};
        let shouldUpdateActiveId = null;

        data.conversations.forEach(convo => {
          // 1. Mapear a estrutura do backend para o estado React
          const lastMessage = convo.messages.length > 0 ? convo.messages[convo.messages.length - 1] : { content: 'Nova Conversa', sender: 'system', timestamp: 0 };

          newConversations[convo.id] = {
            id: convo.id,
            name: convo.name,
            lastMessage: lastMessage.content,
            lastUpdated: lastMessage.timestamp * 1000,
            messages: convo.messages,
            unread: !conversations[convo.id] || (lastMessage.sender === 'cliente' && convo.id !== activeConversationId),
          };

          // 2. Mapear sugestões
          const mappedSuggestions = convo.suggestions.map((s, index) => ({
              id: `${convo.id}-${lastMessage.timestamp}-${index}`,
              query: lastMessage.content,
              private_query: null,
              is_private: false,
              follow_up_options: [{ text: s.text, is_recommended: s.is_recommended }],
              immediate_answer: s.immediate_answer || null,
          }));

          newSuggestionsByConvo[convo.id] = mappedSuggestions;
          newStagesByConvo[convo.id] = convo.stage_id;

          // Se o activeConversationId for nulo, define a mais recente como ativa
          if (!activeConversationId && convo.messages.length > 0) {
              if (!shouldUpdateActiveId || newConversations[convo.id].lastUpdated > newConversations[shouldUpdateActiveId].lastUpdated) {
                  shouldUpdateActiveId = convo.id;
              }
          }
        });

        setConversations(newConversations);
        setSuggestionsByConvo(newSuggestionsByConvo);
        setStagesByConvo(newStagesByConvo);

        if (!activeConversationId && shouldUpdateActiveId) {
            setActiveConversationId(shouldUpdateActiveId);
        }
      }
    } catch (err) {
      console.error("Erro no polling de conversas:", err);
    }
  }, [activeConversationId, conversations]);

  // --- EFEITO PARA INICIAR O POLLING ---
  useEffect(() => {
    fetchConversations();
    const intervalId = setInterval(fetchConversations, 3000);
    return () => clearInterval(intervalId);
  }, [fetchConversations]);


  // --- FUNÇÕES DE LÓGICA DE NEGÓCIO ---

  // Função auxiliar para MOCK de mensagens do cliente (para testing manual)
  const addMessageToActiveConversation = (message) => {
    setConversations(prev => {
      const activeConvo = prev[activeConversationId];
      if (!activeConvo) return prev;

      const updatedMessages = [...activeConvo.messages, message];
      let newLastMessage = message.type === 'audio' ? '🎤 Mensagem de áudio' : message.text;
      if (message.sender === 'vendedor') { newLastMessage = `*Vendedor*: ${newLastMessage}`; }

      const updatedConvo = { ...activeConvo, messages: updatedMessages, lastMessage: newLastMessage, lastUpdated: Date.now() };
      return { ...prev, [activeConversationId]: updatedConvo };
    });

    // MOCK: Se o vendedor ou o cliente digitarem manualmente, envia para indexação
    if (message.sender === 'cliente' || message.sender === 'vendedor') {
        try {
            fetch('http://127.0.0.1:8000/webhook/evolution', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    event: "MESSAGES_UPSERT",
                    instance: "frontend_chat_manual",
                    data: {
                        messages: [{
                            key: { remoteJid: activeConversationId, fromMe: message.sender === 'vendedor', id: `frontend_${Date.now()}` },
                            message: { conversation: message.text }
                        }]
                    },
                    timestamp: Math.floor(Date.now() / 1000)
                }),
            });
            console.log(`INFO: Mensagem do '${message.sender}' (MOCK) enviada para a memória do backend.`);
        } catch (err) {
            console.error("ERRO: Falha ao enviar mensagem MOCK para o backend.", err);
        }
    }

  };

  const handleCustomerMessageSubmit = (query) => {
    // Para testar o fluxo completo, as mensagens do cliente devem vir do webhook real.
    // Usamos esta função apenas para MOCK no frontend, forçando a indexação no backend.
    addMessageToActiveConversation({ sender: 'cliente', text: query, timestamp: Date.now()/1000 });
  };

  const handleConversationSelect = (convoId) => {
    setActiveConversationId(String(convoId));
    setConversations(prev => {
      if (prev[convoId] && prev[convoId].unread) {
        const updatedConvo = { ...prev[convoId], unread: false };
        return { ...prev, [convoId]: updatedConvo };
      }
      return prev;
    });
  };

  // --- FUNÇÃO CORRIGIDA E RENOMEADA PARA ENVIO REAL ---
  const handleUseSuggestion = async (suggestionId, suggestionText, suggestionType) => {
    // 1. CHAMA O ENDPOINT REAL DE ENVIO (Evolution API via backend)
    try {
        const response = await fetch('http://127.0.0.1:8000/send_seller_message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                conversation_id: activeConversationId,
                message_text: suggestionText
            }),
        });

        if (!response.ok) {
            throw new Error('Falha ao enviar mensagem via Evolution API.');
        }
        console.log('Mensagem enviada para o WhatsApp. O Polling irá atualizar a conversa.');

        // 2. Remove a sugestão localmente
        setSuggestionsByConvo(prevMap => {
            const currentSuggestions = prevMap[activeConversationId] || [];
            const updatedSuggestions = currentSuggestions.map(suggestion => {
                if (suggestion.id !== suggestionId) return suggestion;
                // Lógica de remoção/atualização
                const updatedSuggestion = { ...suggestion };
                if (suggestionType === 'immediate_answer') updatedSuggestion.immediate_answer = null;
                else if (suggestionType === 'text_options') updatedSuggestion.text_options = [];
                else if (suggestionType === 'follow_up_options') updatedSuggestion.follow_up_options = [];

                return updatedSuggestion;
            });
            const finalSuggestions = updatedSuggestions.filter(s => s.immediate_answer || (s.follow_up_options && s.follow_up_options.length > 0) || s.text_options.length > 0 || s.video );
            return { ...prevMap, [activeConversationId]: finalSuggestions };
        });

    } catch (err) {
        setError(err.message);
        console.error("ERRO: Falha ao enviar mensagem via Evolution API.", err);
    }
  };


  // --- O RESTANTE DAS FUNÇÕES AUXILIARES ---

  const handleSuggestionRequest = async (query) => {
    setIsLoading(true);
    setError('');
    // Garante que a mensagem foi adicionada ao RAG (via MOCK ou Webhook)
    const currentStage = stagesByConvo[activeConversationId] || null;
    try {
      const response = await fetch('http://127.0.0.1:8000/generate_response', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query, conversation_id: activeConversationId, current_stage_id: currentStage }),
      });
      if (!response.ok) { throw new Error((await response.json()).detail); }
      const data = await response.json();
      if (data.status === 'success') {
        const newSuggestion = { id: Date.now(), query: query, private_query: null, is_private: false, ...data.suggestions };
        setSuggestionsByConvo(prevMap => ({ ...prevMap, [activeConversationId]: [newSuggestion, ...(prevMap[activeConversationId] || [])] }));
        if (data.new_stage_id) { setStagesByConvo(prev => ({ ...prev, [activeConversationId]: data.new_stage_id })); }
      }
    } catch (err) {
      setError(err.message);
      console.error("Falha na requisição:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePrivateSuggestionRequest = async (privateQuery) => {
    setIsLoading(true);
    setError('');
    const currentStage = stagesByConvo[activeConversationId] || null;
    try {
        const response = await fetch('http://127.0.0.1:8000/generate_response', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: privateQuery, conversation_id: activeConversationId, current_stage_id: currentStage }),
        });
        if (!response.ok) { throw new Error((await response.json()).detail); }
        const data = await response.json();
        if (data.status === 'success') {
            const newSuggestion = { id: Date.now(), query: null, private_query: privateQuery, is_private: true, ...data.suggestions };
            setSuggestionsByConvo(prevMap => ({ ...prevMap, [activeConversationId]: [newSuggestion, ...(prevMap[activeConversationId] || [])] }));
            if (data.new_stage_id) { setStagesByConvo(prev => ({ ...prev, [activeConversationId]: data.new_stage_id })); }
        }
    } catch (err) {
        setError(err.message);
        console.error("Falha na requisição privada:", err);
    } finally {
        setIsLoading(false);
    }
  };

  const handleDeleteSuggestion = (suggestionId) => {
    setSuggestionsByConvo(prevMap => {
      const currentSuggestions = prevMap[activeConversationId] || [];
      const finalSuggestions = currentSuggestions.filter(s => s.id !== suggestionId);
      return { ...prevMap, [activeConversationId]: finalSuggestions };
    });
  };

  const useAudio = (suggestionId, audioSrc) => {
    // Por enquanto, apenas remove a sugestão localmente.
    setSuggestionsByConvo(prevMap => ({ ...prevMap, [activeConversationId]: (prevMap[activeConversationId] || []).filter(s => s.id !== suggestionId) }));
    // A lógica de envio de áudio via Evolution API deve ser implementada em handleUseSuggestion
  };

  const handleClearSuggestions = () => {
    setSuggestionsByConvo(prevMap => ({ ...prevMap, [activeConversationId]: [] }));
  };


  // --- RENDERIZAÇÃO ---
  const activeConversation = conversations[activeConversationId] || { id: activeConversationId, messages: [], lastMessage: 'Nenhuma conversa carregada', name: 'Carregando...', lastUpdated: 0 };
  const activeSuggestions = suggestionsByConvo[activeConversationId] || [];
  const sortedConversations = Object.values(conversations).sort((a, b) => b.lastUpdated - a.lastUpdated);

  return (
    <div className="app-container">
      <ConversationList conversations={sortedConversations} activeConversationId={activeConversationId} onConversationSelect={handleConversationSelect} />
      <ChatPanel
        key={activeConversationId}
        activeConversation={activeConversation}
        onCustomerQuerySubmit={handleCustomerMessageSubmit}
        // O envio do campo de texto agora dispara a sugestão real
        onSellerResponseSubmit={(text) => handleUseSuggestion(Date.now(), text, 'follow_up_options')}
        isLoading={isLoading}
      />
      <CopilotPanel
        isLoading={isLoading}
        error={error}
        suggestions={activeSuggestions}
        onUseSuggestion={handleUseSuggestion} // Renomeado
        onUseAudio={useAudio}
        onClearSuggestions={handleClearSuggestions}
        onMessageDrop={handleSuggestionRequest}
        onPrivateQuerySubmit={handlePrivateSuggestionRequest}
        onDeleteSuggestion={handleDeleteSuggestion}
      />
    </div>
  );
}

export default App;
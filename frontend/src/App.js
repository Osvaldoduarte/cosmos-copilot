// Arquivo: frontend/src/App.js (Versão Final e Corrigida)

import React, { useState } from 'react';
import ConversationList from './components/ConversationList';
import ChatPanel from './components/ChatPanel';
import CopilotPanel from './components/CopilotPanel';
import { initialConversationsData } from './initialData';

function App() {
  const [conversations, setConversations] = useState(initialConversationsData);
  const [activeConversationId, setActiveConversationId] = useState('1');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [suggestionsByConvo, setSuggestionsByConvo] = useState({});
  const [stagesByConvo, setStagesByConvo] = useState({});

  const addMessageToActiveConversation = (message) => {
    setConversations(prev => {
      const activeConvo = prev[activeConversationId];
      const updatedMessages = [...activeConvo.messages, message];
      let newLastMessage = message.type === 'audio' ? '🎤 Mensagem de áudio' : message.text;
      if (message.sender === 'vendedor') {
        newLastMessage = `*Cristiano*: ${newLastMessage}`;
      }
      const updatedConvo = { ...activeConvo, messages: updatedMessages, lastMessage: newLastMessage, lastUpdated: Date.now() };
      return { ...prev, [activeConversationId]: updatedConvo };
    });

    if (message.sender === 'cliente' || message.sender === 'vendedor') {
      try {
        fetch('http://127.0.0.1:8000/webhook/evolution', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            instance: "frontend_update",
            sender: "me",
            data: {
              key: { remoteJid: activeConversationId, fromMe: message.sender === 'vendedor', id: `frontend_${Date.now()}` },
              message: { conversation: message.text }
            },
            timestamp: Math.floor(Date.now() / 1000)
          }),
        });
        console.log(`INFO: Mensagem do '${message.sender}' enviada para a memória do backend.`);
      } catch (err) {
        console.error("ERRO: Falha ao enviar mensagem para a memória do backend.", err);
      }
    }
  };

  const handleCustomerMessageSubmit = (query) => {
    addMessageToActiveConversation({ sender: 'cliente', text: query });
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

  const handleSuggestionRequest = async (query) => {
    setIsLoading(true);
    setError('');
    const activeConvo = conversations[activeConversationId];
    if (!activeConvo.messages.find(msg => msg.text === query && msg.sender === 'cliente')) {
        addMessageToActiveConversation({ sender: 'cliente', text: query });
    }
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
            // A CORREÇÃO ESTÁ AQUI: Adicionamos is_private: true
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

  const useSuggestion = (suggestionId, suggestionText, suggestionType) => {
    addMessageToActiveConversation({ sender: 'vendedor', text: suggestionText });
    setSuggestionsByConvo(prevMap => {
      const currentSuggestions = prevMap[activeConversationId] || [];
      const updatedSuggestions = currentSuggestions.map(suggestion => {
        if (suggestion.id !== suggestionId) return suggestion;
        return { ...suggestion, [suggestionType]: null };
      });
      const finalSuggestions = updatedSuggestions.filter(s => s.immediate_answer || (s.follow_up_options && s.follow_up_options.length > 0) || s.video );
      return { ...prevMap, [activeConversationId]: finalSuggestions };
    });
  };

  const useAudio = (suggestionId, audioSrc) => {
    addMessageToActiveConversation({ sender: 'vendedor', type: 'audio', src: audioSrc });
    setSuggestionsByConvo(prevMap => ({ ...prevMap, [activeConversationId]: (prevMap[activeConversationId] || []).filter(s => s.id !== suggestionId) }));
  };

  const handleClearSuggestions = () => {
    setSuggestionsByConvo(prevMap => ({ ...prevMap, [activeConversationId]: [] }));
  };

  const activeConversation = conversations[activeConversationId];
  const activeSuggestions = suggestionsByConvo[activeConversationId] || [];
  const sortedConversations = Object.values(conversations).sort((a, b) => b.lastUpdated - a.lastUpdated);

  return (
    <div className="app-container">
      <ConversationList conversations={sortedConversations} activeConversationId={activeConversationId} onConversationSelect={handleConversationSelect} />
      <ChatPanel key={activeConversationId} activeConversation={activeConversation} onCustomerQuerySubmit={handleCustomerMessageSubmit} onSellerResponseSubmit={(text) => addMessageToActiveConversation({sender: 'vendedor', text})} isLoading={isLoading} />
      <CopilotPanel
        isLoading={isLoading}
        error={error}
        suggestions={activeSuggestions}
        onUseSuggestion={useSuggestion}
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
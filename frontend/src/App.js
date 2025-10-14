import React, { useState, useEffect, useCallback } from 'react';
import ConversationList from './components/ConversationList';
import ChatPanel from './components/ChatPanel';
import CopilotPanel from './components/CopilotPanel';
import { initialMockConversations } from './initialData'; // Mantenha o import se for usar mock para debug


function App() {
  // --- ESTADOS INICIAIS ---
  // Inicia com estado vazio (conversas reais) ou use initialMockConversations para debug
  const [conversations, setConversations] = useState({});
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [suggestionsByConvo, setSuggestionsByConvo] = useState({});
  const [stagesByConvo, setStagesByConvo] = useState({});


  // --- FUNÇÕES DE LÓGICA DO VENDEDOR ---

  // Função para usar sugestão e enviá-la ao cliente (completa e corrigida)
  const handleUseSuggestion = async (suggestionId, suggestionText, suggestionField) => {
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

        if (!response.ok) { throw new Error('Falha ao enviar mensagem via Evolution API.'); }
        console.log('Mensagem enviada para o WhatsApp. O Polling irá atualizar a conversa.');

        // 2. Remove a sugestão localmente
        setSuggestionsByConvo(prevMap => {
            const currentSuggestions = prevMap[activeConversationId] || [];

            const updatedSuggestions = currentSuggestions.map(suggestion => {
                if (suggestion.id !== suggestionId) return suggestion;

                const updatedSuggestion = { ...suggestion };

                if (suggestionField === 'immediate_answer') {
                    updatedSuggestion.immediate_answer = null;
                } else if (suggestionField === 'follow_up_options') {
                    updatedSuggestion.follow_up_options = [];
                }

                return updatedSuggestion;
            });

            const finalSuggestions = updatedSuggestions.filter(s =>
                s.immediate_answer ||
                (s.follow_up_options && s.follow_up_options.length > 0) ||
                s.video
            );

            return { ...prevMap, [activeConversationId]: finalSuggestions };
        });

    } catch (err) {
        setError(err.message);
        console.error("ERRO: Falha ao enviar mensagem via Evolution API.", err);
    }
  };

  // Funções de solicitação de sugestão (handleSuggestionRequest e handlePrivateSuggestionRequest)
  const handleSuggestionRequest = async (query) => {
    setIsLoading(true);
    setError('');
    const currentStage = stagesByConvo[activeConversationId] || null;
    try {
      const response = await fetch('http://127.0.0.1:8000/generate_response', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query, conversation_id: activeConversationId, current_stage_id: currentStage }),
      });
      if (!response.ok) { throw new Error((await response.json()).detail || "Erro desconhecido ao gerar sugestões."); }

      const data = await response.json();

      if (data.status === 'success') {
        // 1. Cria a nova sugestão com os dados completos do backend
        const newSuggestion = {
            id: Date.now(),
            query: query,
            private_query: null,
            is_private: false,
            ...data.suggestions // Inclui immediate_answer, follow_up_options, video
        };

        // 2. Adiciona a sugestão ao topo da lista
        setSuggestionsByConvo(prevMap => ({
            ...prevMap,
            [activeConversationId]: [newSuggestion, ...(prevMap[activeConversationId] || [])]
        }));

        // 3. Atualiza o estágio da conversa (Cérebro 3)
        if (data.new_stage_id) {
            setStagesByConvo(prev => ({
                ...prev,
                [activeConversationId]: data.new_stage_id
            }));
        }
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
        if (!response.ok) { throw new Error((await response.json()).detail || "Erro desconhecido ao gerar sugestões privadas."); }

        const data = await response.json();

        if (data.status === 'success') {
            // 1. Cria a nova sugestão como privada
            const newSuggestion = {
                id: Date.now(),
                query: null,
                private_query: privateQuery,
                is_private: true,
                ...data.suggestions // Inclui immediate_answer, follow_up_options, video
            };

            // 2. Adiciona a sugestão ao topo da lista
            setSuggestionsByConvo(prevMap => ({
                ...prevMap,
                [activeConversationId]: [newSuggestion, ...(prevMap[activeConversationId] || [])]
            }));

            // 3. Atualiza o estágio da conversa (Cérebro 3)
            if (data.new_stage_id) {
                setStagesByConvo(prev => ({
                    ...prev,
                    [activeConversationId]: data.new_stage_id
                }));
            }
        }
    } catch (err) {
        setError(err.message);
        console.error("Falha na requisição privada:", err);
    } finally {
        setIsLoading(false);
    }
  };

  // Função handleConversationSelect (final)
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

  const handleCustomerMessageSubmit = (query) => {
    // Para testar o fluxo completo, as mensagens do cliente devem vir do webhook real.
    // Usamos esta função apenas para MOCK no frontend, forçando a indexação no backend.
    // Se não for MOCK, o ideal é que esta função chame handleSuggestionRequest(query)
    // Se for MOCK, você deve restaurar a função addMessageToActiveConversation
  };

  const handleClearSuggestions = () => {
    setSuggestionsByConvo(prevMap => ({ ...prevMap, [activeConversationId]: [] }));
  };
  // ... (Outras funções como handleDeleteSuggestion, useAudio devem ser restauradas)


  // --- FUNÇÃO DE POLLING CORRIGIDA (CRÍTICA) ---
  const fetchConversations = useCallback(async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/conversations');
      if (!response.ok) { throw new Error('Falha ao buscar conversas do backend.'); }
      const data = await response.json();

      if (data.status === 'success' && data.conversations) {
        const newConversations = {};
        const newSuggestionsByConvo = {};
        const newStagesByConvo = {};
        const existingConversations = conversations;

        data.conversations.forEach(convo => {

          const messagesArray = convo.messages || [];
          const lastMessage = messagesArray.length > 0 ? messagesArray[messagesArray.length - 1] : { content: 'Nova Conversa', sender: 'system', timestamp: 0 };

          // CRÍTICO: Mapeamento de 'content' (backend) para 'text' (ChatPanel)
          const mappedMessages = messagesArray.map(msg => ({
              sender: msg.sender,
              text: msg.content,  // <--- CORREÇÃO FUNDAMENTAL
              timestamp: msg.timestamp
          }));

          // --- Mapeamento de Sugestões (Simplificado para o formato final) ---
          const currentSuggestions = convo.suggestions && convo.suggestions.length > 0 ? convo.suggestions[0] : {};

          const mappedSuggestions = [{
              id: `${convo.id}-${lastMessage.timestamp}`,
              query: lastMessage.content,
              private_query: null,
              is_private: false,
              immediate_answer: currentSuggestions.immediate_answer || null,
              follow_up_options: currentSuggestions.follow_up_options || [],
              video: currentSuggestions.video || null,
          }].filter(s => s.immediate_answer || (s.follow_up_options && s.follow_up_options.length > 0) || s.video);

          // --- ATUALIZAÇÃO DO OBJETO DE CONVERSA ---
          const isUnread = existingConversations[convo.id]
            ? (lastMessage.sender === 'cliente' && convo.id !== activeConversationId)
            : true;

          newConversations[convo.id] = {
            id: convo.id,
            name: convo.name || convo.id.split('@')[0],
            lastMessage: lastMessage.content,
            lastUpdated: lastMessage.timestamp * 1000,
            messages: mappedMessages, // <--- ARRAY DE MENSAGENS CORRIGIDO
            unread: isUnread,
          };

          newSuggestionsByConvo[convo.id] = mappedSuggestions;
          newStagesByConvo[convo.id] = convo.stage_id;

        });

        // Atualiza o estado:
        setConversations(newConversations);
        setSuggestionsByConvo(newSuggestionsByConvo);
        setStagesByConvo(newStagesByConvo);

        // --- LÓGICA DE ATIVAÇÃO DE ID (GARANTE QUE O CHAT NÃO FIQUE VAZIO) ---
        if (!activeConversationId && Object.keys(newConversations).length > 0) {
            const sorted = Object.values(newConversations).sort((a, b) => b.lastUpdated - a.lastUpdated);
            if (sorted.length > 0) {
                setActiveConversationId(sorted[0].id);
            }
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


  // --- RENDERIZAÇÃO ---
  const activeConversation = conversations[activeConversationId] || { id: null, messages: [], lastMessage: 'Nenhuma conversa carregada', name: 'Carregando...', lastUpdated: 0 };
  const activeSuggestions = suggestionsByConvo[activeConversationId] || [];
  const sortedConversations = Object.values(conversations).sort((a, b) => b.lastUpdated - a.lastUpdated);

  return (
    <div className="app-container">
      <ConversationList conversations={sortedConversations} activeConversationId={activeConversationId} onConversationSelect={handleConversationSelect} />
      <ChatPanel
        key={activeConversationId}
        activeConversation={activeConversation}
        onCustomerQuerySubmit={handleCustomerMessageSubmit}
        onSellerResponseSubmit={(text) => handleUseSuggestion(Date.now(), text, 'follow_up_options')}
        isLoading={isLoading}
      />
      <CopilotPanel
        isLoading={isLoading}
        error={error}
        suggestions={activeSuggestions}
        onUseSuggestion={handleUseSuggestion}
        // ... (o restante das props)
      />
    </div>
  );
}

export default App;
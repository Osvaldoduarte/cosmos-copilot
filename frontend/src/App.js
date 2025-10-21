import React, { useState, useEffect, useCallback } from 'react';
import ConversationList from './components/ConversationList';
import ChatPanel from './components/ChatPanel';
import CopilotPanel from './components/CopilotPanel';
import NewConversationModal from './components/NewConversationModal';
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import Login from './components/Login';

import Drawer from 'react-modern-drawer';
import 'react-modern-drawer/dist/index.css';

function App() {
  // --- ESTADOS INICIAIS ---
  const [token, setToken] = useState(localStorage.getItem('authToken')); // Tenta pegar o token salvo
  const [loginError, setLoginError] = useState('');
  const [isLoginLoading, setIsLoginLoading] = useState(false);  // Inicia com estado vazio (conversas reais) ou use initialMockConversations para debug

  const [conversations, setConversations] = useState({});
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [suggestionsByConvo, setSuggestionsByConvo] = useState({});
  const [stagesByConvo, setStagesByConvo] = useState({});
  const [isModalOpen, setIsModalOpen] = useState(false);

  const [isCopilotOpen, setIsCopilotOpen] = useState(false);
  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';

  // --- LÓGICA DE RESPONSIVIDADE ---
  // Um estado simples para saber se estamos em uma tela "mobile"
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);

  const handleLogout = () => {
    localStorage.removeItem('authToken');
    setToken(null);
    setConversations({}); // Limpa os dados
    setActiveConversationId(null);
  };

  const fetchWithAuth = useCallback(async (url, options = {}) => {
    const token = localStorage.getItem('authToken');

    // Prepara os cabeçalhos, adicionando o de Autorização
    const headers = {
      ...options.headers,
      'Authorization': `Bearer ${token}`
    };

    const fullUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`;
    const response = await fetch(fullUrl, { ...options, headers });

    // Se o token for inválido ou expirar, o backend retornará 401.
    // Nesse caso, fazemos o logout automático do usuário.
    if (response.status === 401) {
      handleLogout();
      // Lança um erro para parar a execução da função que chamou o fetch.
      throw new Error('Sessão expirada. Por favor, faça login novamente.');
    }

    return response;
  }, []);

const fetchConversations = useCallback(async () => {
    try {
      const response = await fetchWithAuth('/conversations');
      if (!response.ok) { throw new Error('Falha ao buscar conversas.'); }
      const data = await response.json();

      if (data.status === 'success' && data.conversations) {
        const newConversations = {};
        const newStagesByConvo = {};

        data.conversations.forEach(convo => {
          const messagesArray = convo.messages || [];

          // =====================================================================
          // VOLTAMOS A USAR O OBJETO lastMessage consistentemente
          // =====================================================================
          const lastMessage = messagesArray.length > 0
              ? messagesArray[messagesArray.length - 1]
              : { content: 'Nova Conversa', sender: 'system', timestamp: 0 };
          // Usamos o timestamp da última mensagem ou o lastUpdated do backend, o que for mais recente
          const lastTimestampMs = Math.max(
              convo.lastUpdated || 0,
              lastMessage.timestamp * 1000 || 0
          );
          // =====================================================================

          // Mapeamento de mensagens (continua igual)
          const mappedMessages = messagesArray.map(msg => ({
              sender: msg.sender,
              text: msg.content,
              timestamp: msg.timestamp,
              message_id: msg.message_id || `${msg.sender}-${msg.timestamp}`
          }));

          // Mapeamento de Sugestões (agora usa lastMessage corretamente)
          // (Removido pois não está sendo usado para atualizar o estado)
          /* const currentSuggestions = convo.suggestions && convo.suggestions.length > 0 ? convo.suggestions[0] : {};
          const mappedSuggestions = [{
              id: `${convo.id}-${lastMessage.timestamp}`, // Usa lastMessage
              query: lastMessage.content, // Usa lastMessage
              // ... resto do mapeamento ...
          }].filter(s => s.immediate_answer || (s.follow_up_options && s.follow_up_options.length > 0) || s.video);
          */

          // Lógica de Unread (continua igual)
          const isUnread = convo.unread || false;

          // Atualização do Objeto de Conversa (agora usa lastMessage corretamente)
          console.log(`[fetchConversations] Dados recebidos para ${convo.id}: unreadCount = ${convo.unreadCount}, unread = ${convo.unread}`);
          newConversations[convo.id] = {
            id: convo.id,
            name: convo.name || convo.id.split('@')[0],
            avatarUrl: convo.avatar_url,
            lastMessage: lastMessage.content, // Usa lastMessage
            lastUpdated: lastTimestampMs,     // Usa o timestamp calculado
            messages: mappedMessages,
            unread: isUnread,
            unreadCount: convo.unreadCount || 0,
            clientData: convo.dados_cliente || {},
          };
          newStagesByConvo[convo.id] = convo.stage_id;

          // NOTA: A lógica que atualizava suggestionsByConvo foi removida daqui,
          // pois ela estava causando o "pisca-some" e não era necessária no polling.
          // O estado de sugestões é gerenciado pelas funções handleSuggestionRequest.
        });

        setConversations(newConversations);
        setStagesByConvo(newStagesByConvo);
      }
    } catch (err) { console.error("Erro no polling:", err); }
  }, [fetchWithAuth]); // Dependência correta

  useEffect(() => {
    const savedToken = localStorage.getItem('authToken');
    if (savedToken) {
      setToken(savedToken);
    }
  }, []);

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    const handleKeyDown = (event) => {
      // Verifica se a tecla pressionada foi 'Escape'
      if (event.key === 'Escape') {
        // Limpa o ID da conversa ativa, deselecionando-a
        setActiveConversationId(null);
      }
    };

    // Adiciona o "ouvinte" de eventos ao carregar o componente
    window.addEventListener('keydown', handleKeyDown);

    // Função de limpeza: remove o "ouvinte" ao desmontar o componente
    // para evitar vazamentos de memória.
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  const handleLogin = async (username, password) => {
    setIsLoginLoading(true);
    setLoginError('');
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          'username': username,
          'password': password
        })
      });

      if (!response.ok) {
        throw new Error('Usuário ou senha inválidos.');
      }

      const data = await response.json();
      const authToken = data.access_token;

      localStorage.setItem('authToken', authToken); // Salva o token no navegador
      setToken(authToken); // Atualiza o estado para mostrar a aplicação

    } catch (err) {
      setLoginError(err.message);
    } finally {
      setIsLoginLoading(false);
    }
  };


const handleToggleCopilot = () => {
    setIsCopilotOpen(prevState => !prevState);
  };

  const handleBackToList = () => {
    setActiveConversationId(null); // Limpa a conversa ativa, fazendo a UI voltar para a lista
  };

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
  const handleStartConversation = async (number, message) => {
    setIsLoading(true);
    setError('');
    try {
      const response = await fetch('http://127.0.0.1:8000/conversations/start_new', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recipient_number: number,
          initial_message: message,
        }),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Falha ao iniciar a conversa.');
      }

      setIsModalOpen(false); // Fecha o modal em caso de sucesso
      // O polling se encarregará de atualizar a lista
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSuggestionRequest = async (query) => {
  if (isMobile) {
      setIsCopilotOpen(true);
    }
    // ===================================================================

    setIsLoading(true);
    setError('');
    const currentStage = stagesByConvo[activeConversationId] || null;


    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/generate_response', {
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
        const response = await fetchWithAuth('http://127.0.0.1:8000/generate_response', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: privateQuery, conversation_id: activeConversationId, current_stage_id: currentStage, is_private_query: true }),
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
const handleConversationSelect = useCallback(async (convoId) => {
    const stringConvoId = String(convoId);
    console.log(`[handleConversationSelect] Selecionada conversa: ${stringConvoId}`);
    setActiveConversationId(stringConvoId);

    // APENAS NOTIFICA O BACKEND. A UI será atualizada pelo próximo polling.
    try {
      console.log(`[handleConversationSelect] Notificando backend /mark-read...`);
      await fetchWithAuth(`http://127.0.0.1:8000/conversations/${encodeURIComponent(stringConvoId)}/mark-read`, {
          method: 'POST',
      });
      console.log(`[Frontend] Notificado backend sobre leitura da conversa ${stringConvoId}.`);
      // FORÇAR ATUALIZAÇÃO (Opcional, se o polling demorar muito):
      // fetchConversations();
    } catch (error) {
      console.error(`[Frontend] Erro ao notificar backend sobre leitura da conversa ${stringConvoId}:`, error);
    }
  }, [fetchWithAuth]); // Removido 'conversations' da dependência

  const handleCustomerMessageSubmit = (query) => {
    // Para testar o fluxo completo, as mensagens do cliente devem vir do webhook real.
    // Usamos esta função apenas para MOCK no frontend, forçando a indexação no backend.
    // Se não for MOCK, o ideal é que esta função chame handleSuggestionRequest(query)
    // Se for MOCK, você deve restaurar a função addMessageToActiveConversation
  };

  const handleClearSuggestions = () => {
    setSuggestionsByConvo(prevMap => ({ ...prevMap, [activeConversationId]: [] }));
  };
const handleDeleteSuggestion = (suggestionId) => {
    setSuggestionsByConvo(prevMap => {
      const currentSuggestions = prevMap[activeConversationId] || [];
      const updatedSuggestions = currentSuggestions.filter(s => s.id !== suggestionId);
      return { ...prevMap, [activeConversationId]: updatedSuggestions };
    });
  };

const handleMessageDrop = (droppedText) => {
  // Quando uma mensagem do cliente é solta, tratamos como uma nova
  // solicitação de sugestão.
  console.log(`Mensagem arrastada recebida: "${droppedText}". Solicitando sugestão...`);
  handleSuggestionRequest(droppedText);
}; // useCallback com array vazio garante que a função não seja recriada desnecessariamente

  // --- EFEITO PARA INICIAR O POLLING ---
useEffect(() => {
    let intervalId = null;

    if (token) {
      console.log("[Polling] Token válido. Iniciando busca inicial e intervalo.");
      fetchConversations();

      intervalId = setInterval(fetchConversations, 5000);
      console.log(`[Polling] Intervalo iniciado (ID: ${intervalId}).`);
    } else {
      console.log("[Polling] Sem token. Polling não iniciado.");
    }

    // FUNÇÃO DE LIMPEZA (executa no logout ou desmontagem)
    return () => {
      if (intervalId) {
        clearInterval(intervalId);
        console.log(`[Polling] Intervalo parado (ID: ${intervalId}).`);
      }
    };
  }, [token]);

  // ======================================================
  // O "PORTEIRO": LÓGICA DE RENDERIZAÇÃO CONDICIONAL
  // ======================================================
  if (!token) {
    // Se NÃO HÁ token, renderiza a tela de login
    return <Login onLogin={handleLogin} error={loginError} isLoading={isLoginLoading} />;
  }


// --- RENDERIZAÇÃO ---
  const activeConversation = conversations[activeConversationId];
  const activeSuggestions = suggestionsByConvo[activeConversationId] || [];
  const unreadCount = Object.values(conversations).reduce((count, convo) => {
    return convo.unread ? count + 1 : count;
  }, 0);


  const sortedConversations = Object.values(conversations).sort((a, b) => b.lastUpdated - a.lastUpdated);



  // O CopilotPanel agora é uma variável para podermos usá-lo em dois lugares (desktop e mobile)
  const copilotComponent = (
    <CopilotPanel
      isLoading={isLoading}
      error={error}
      suggestions={activeSuggestions}
      onUseSuggestion={handleUseSuggestion}
      onDeleteSuggestion={handleDeleteSuggestion}
      onMessageDrop={handleMessageDrop}
      onClearSuggestions={handleClearSuggestions}
      onPrivateQuerySubmit={handlePrivateSuggestionRequest}
    />
  );

  return (
    <>
      <div className="app-container">
        {isMobile ? (
          // --- LÓGICA PARA RENDERIZAÇÃO EM TELAS PEQUENAS (MOBILE) ---
          <>
            {!activeConversationId ? (
              // Se nenhuma conversa estiver ativa, mostra a lista
              <ConversationList
                conversations={sortedConversations}
                activeConversationId={activeConversationId}
                onConversationSelect={handleConversationSelect}
                onNewConversationClick={() => setIsModalOpen(true)}
                onLogout={handleLogout}
              />
            ) : (
              // Se uma conversa estiver ativa, mostra o painel de chat
              <ChatPanel
                key={activeConversationId}
                activeConversationId={activeConversationId}
                activeConversation={conversations[activeConversationId]}
                onSellerResponseSubmit={(text) => handleUseSuggestion(Date.now(), text, 'follow_up_options')}
                isLoading={isLoading}
                onToggleCopilot={handleToggleCopilot}
                unreadCount={unreadCount}
                onBack={handleBackToList}
                onMessageDragAnalyze={handleSuggestionRequest}
                isMobile={isMobile}
              />
            )}
          </>
        ) : (
          // --- LÓGICA PARA RENDERIZAÇÃO EM TELAS GRANDES (DESKTOP) ---
          // NOTA: Se o bug de 33/33/33 persistir, precisamos ajustar o CSS aqui.
          <PanelGroup direction="horizontal">
            <Panel defaultSizePercentage={25} minSizePercentage={15}>
              <ConversationList
                conversations={sortedConversations}
                activeConversationId={activeConversationId}
                onConversationSelect={handleConversationSelect}
                onNewConversationClick={() => setIsModalOpen(true)}
                onLogout={handleLogout}
              />
            </Panel>

            <PanelResizeHandle />

            <Panel defaultSizePercentage={50} minSizePercentage={30}>
              <ChatPanel
                key={activeConversationId}
                activeConversationId={activeConversationId}
                activeConversation={conversations[activeConversationId]}
                onSellerResponseSubmit={(text) => handleUseSuggestion(Date.now(), text, 'follow_up_options')}
                isLoading={isLoading}
                onMessageDragAnalyze={handleSuggestionRequest}
                isMobile={isMobile}
              />
            </Panel>

            <PanelResizeHandle />

            <Panel defaultSizePercentage={25} minSizePercentage={20}>
              {copilotComponent}
            </Panel>
          </PanelGroup>
        )}
      </div>

      {/* --- O PAINEL DESLIZANTE (DRAWER) PARA MOBILE --- */}
      {/* Ele vive fora do layout principal e só é renderizado em telas mobile */}
      {isMobile && (
        <Drawer
            open={isCopilotOpen}
            onClose={() => setIsCopilotOpen(false)}
            direction='right'
            size={'80vw'} // Ocupa 80% da largura da tela, como você sugeriu
            className='copilot-drawer'
        >
            {/* O conteúdo do painel deslizante é o nosso CopilotPanel */}
            {copilotComponent}
        </Drawer>
      )}

      {/* O Modal de Nova Conversa continua aqui, para flutuar sobre tudo */}
      <NewConversationModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onStartConversation={handleStartConversation}
        isLoading={isLoading}
      />
    </>
  );
  return (
    <>
      {/* ... cole aqui o seu return antigo completo, desde <div className="app-container"> até o final ... */}
      {/* Lembre-se de adicionar um botão de Logout em algum lugar, por exemplo, no ConversationList */}
    </>
  );
}



export default App;
// frontend/src/initialData.js
// Mock de dados com mensagens reais e um estágio ativo
export const initialMockConversations = {

  // --- CONVERSA 1: CLIENTE ATIVO (TESTE DE COPILOT E QUALIFICAÇÃO) ---
  '5511999999999@s.whatsapp.net': {
    id: '5511999999999@s.whatsapp.net',
    name: 'Cliente Teste (Mock)',
    contact_name: 'João da Alpha Tech', // 💡 Nome completo
    avatar_url: 'https://i.pravatar.cc/150?img=1', // 💡 Avatar mock
    // O lastMessage é usado para o snippet da lista de conversas
    lastMessage: 'Queria saber como faço a qualificação de leads.',
    timestamp: Math.floor(Date.now() / 1000) - 60, // Unix Timestamp
    lastUpdated: Date.now() - 60000, // 1 minuto atrás
    messages: [
        { sender: 'cliente', content: 'Oi, tudo bem?', timestamp: Math.floor(Date.now() / 1000) - 300 },
        { sender: 'vendedor', content: 'Olá! Sim, e com você? Qual seu nome e empresa?', timestamp: Math.floor(Date.now() / 1000) - 240 },
        { sender: 'cliente', content: 'Eu sou o João da Alpha Tech. Queria saber como faço a qualificação de leads.', timestamp: Math.floor(Date.now() / 1000) - 60, media_type: 'text' },
    ],
    unread: 1,
    // Sugestões mockadas (para verificar o CopilotPanel.js)
    suggestions: [
        {
            id: 'mock_sug_1',
            query: 'Como faço a qualificação de leads?',
            is_private: false,
            immediate_answer: "O processo de qualificação de leads no CosmosERP é feito através da nossa trilha de Playbook de Vendas, que se inicia na Qualificação Inicial.",
            follow_up_options: [
                { text: "Qual seu principal desafio hoje na Alpha Tech?", is_recommended: true }
            ],
            // Sugestão de vídeo para testar o VideoSuggestionCard
            video: {
                title: "Como qualificar leads no CosmosERP",
                url: "https://www.youtube.com/watch?v=LZoLvV7p25A" // 💡 URL completo
            }
        }
    ],
    stage_id: "stage_qualification" // Estágio de qualificação
  },

  // --- CONVERSA 2: CLIENTE ANTIGO (TESTE DE MÍDIA) ---
  '5511888888888@s.whatsapp.net': {
    id: '5511888888888@s.whatsapp.net',
    name: 'Cliente Antigo (Mock)',
    contact_name: 'Maria da Beta Corp',
    avatar_url: 'https://i.pravatar.cc/150?img=2',
    lastMessage: 'Obrigado!',
    timestamp: Math.floor(Date.now() / 1000) - 7200, // 2 horas atrás
    lastUpdated: Date.now() - 7200000,
    messages: [
        { sender: 'cliente', content: 'Essa funcionalidade é legal.', timestamp: Math.floor(Date.now() / 1000) - 7200, media_type: 'text' },
        { sender: 'cliente', content: 'Aqui está a imagem da tela.', timestamp: Math.floor(Date.now() / 1000) - 6000, media_type: 'image', media_url: 'https://picsum.photos/300/200' },
        { sender: 'vendedor', content: 'Entendido. Vou verificar isso.', timestamp: Math.floor(Date.now() / 1000) - 5800, media_type: 'text' },
    ],
    unread: 0,
    suggestions: [],
    stage_id: "stage_pain_discovery"
  }
};
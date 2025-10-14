//// Mock de dados com mensagens reais e um estágio ativo
//export const initialMockConversations = {
//  // O ID da conversa deve ser o JID do WhatsApp (ex: 5511999999999@s.whatsapp.net)
//  '5511999999999@s.whatsapp.net': {
//    id: '5511999999999@s.whatsapp.net',
//    name: 'Cliente Teste (Mock)',
//    lastMessage: 'Queria saber como faço a qualificação de leads.',
//    lastUpdated: Date.now() - 60000, // 1 minuto atrás
//    messages: [
//        { sender: 'cliente', text: 'Oi, tudo bem?', timestamp: Date.now() - 300000 },
//        { sender: 'vendedor', text: 'Olá! Sim, e com você? Qual seu nome e empresa?', timestamp: Date.now() - 240000 },
//        { sender: 'cliente', text: 'Eu sou o João da Alpha Tech. Queria saber como faço a qualificação de leads.', timestamp: Date.now() - 60000 },
//    ],
//    unread: true,
//    // Sugestões mockadas (para verificar o CopilotPanel.js)
//    suggestions: [
//        {
//            id: 'mock_sug_1',
//            query: 'Como faço a qualificação de leads?',
//            is_private: false,
//            immediate_answer: "O processo de qualificação de leads no CosmosERP é feito através da nossa trilha de Playbook de Vendas, que se inicia na Qualificação Inicial.",
//            follow_up_options: [
//                { text: "Qual seu principal desafio hoje na Alpha Tech?", is_recommended: true }
//            ],
//            // Sugestão de vídeo (se seu VideoSuggestionCard estiver esperando 'url' e 'title')
//            video: {
//                title: "Como qualificar leads no CosmosERP",
//                url: "https://www.youtube.com/embed/LZoLvV7p25A"
//            }
//        }
//    ],
//    stage_id: "stage_qualification" // Estágio de qualificação
//  },
//
//  '5511888888888@s.whatsapp.net': {
//    id: '5511888888888@s.whatsapp.net',
//    name: 'Cliente Antigo (Mock)',
//    lastMessage: 'Obrigado!',
//    lastUpdated: Date.now() - 7200000, // 2 horas atrás
//    messages: [
//        { sender: 'cliente', text: 'Essa funcionalidade é legal.', timestamp: Date.now() - 7200000 },
//    ],
//    unread: false,
//    suggestions: [],
//    stage_id: "stage_pain_discovery"
//  }
//};
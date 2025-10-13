// Arquivo: src/initialData.js

export const initialConversationsData = {
  // Adicionamos a propriedade 'lastUpdated' com um valor numérico (timestamp)
  // para que a função de ordenação possa comparar as conversas.
  '1': { id: 1, name: 'Gladis', avatarUrl: 'https://i.pravatar.cc/150?img=7', lastMessage: 'Ok', timestamp: '6 minutos', messages: [{sender: 'cliente', text: 'Ok'}], unread: false, lastUpdated: 1727876040000 },
  '2': { id: 2, name: 'Gabriela', avatarUrl: 'https://i.pravatar.cc/150?img=8', lastMessage: '*Cristiano*: Oi Gabriela, tudo be...', timestamp: 'cerca de 2 horas', messages: [{sender: 'vendedor', text: 'Oi Gabriela, tudo bem?'}], unread: true, lastUpdated: 1727868840000 },
  '3': { id: 3, name: 'j n doces', avatarUrl: 'https://i.pravatar.cc/150?img=9', lastMessage: 'Bom dia, tudo bem? quanto custa o sistema?', timestamp: 'cerca de 7 horas', messages: [{sender: 'system', text: 'Sessão iniciada.'}], unread: true, lastUpdated: 1727847240000 },
  '4': { id: 4, name: 'Francisco', avatarUrl: 'https://i.pravatar.cc/150?img=10', lastMessage: '*Cristiano*: Perfeito, excelente...', timestamp: '1 dia', messages: [{sender: 'system', text: 'Sessão iniciada.'}], unread: false, lastUpdated: 1727789640000 },
  '5': { id: 5, name: 'Ana Paula - FK Pães', avatarUrl: 'https://i.pravatar.cc/150?img=11', lastMessage: 'Vamos dando nosso feedback tb...', timestamp: '1 dia', messages: [{sender: 'system', text: 'Sessão iniciada.'}], unread: true, lastUpdated: 1727786040000 },
  '6': { id: 6, name: 'Fernando 💎', avatarUrl: 'https://i.pravatar.cc/150?img=12', lastMessage: '👍', timestamp: '2 dias', messages: [{sender: 'system', text: 'Sessão iniciada.'}], unread: false, lastUpdated: 1727703240000 },
  '7': { id: 7, name: 'Elias Pessoa', avatarUrl: 'https://i.pravatar.cc/150?img=1', lastMessage: '*Cristiano*: Oi Elias, bom dia... já...', timestamp: '2 dias', messages: [{sender: 'vendedor', text: 'Oi Elias, bom dia...'}], unread: false, lastUpdated: 1727699640000 },
};
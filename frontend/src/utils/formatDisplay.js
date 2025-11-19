// frontend/src/utils/formatDisplay.js

// URL para uma imagem de perfil padrão no estilo do WhatsApp
export const DEFAULT_AVATAR_URL = 'https://cdn.pixabay.com/photo/2015/10/05/22/37/blank-profile-picture-973460_960_720.png';

export const formatContactName = (name) => {
  if (typeof name !== 'string' || !name) return 'Carregando...';
  if (!name.includes('@')) return name;

  const numberOnly = name.split('@')[0];
  if (numberOnly.startsWith('55') && numberOnly.length === 13) {
    const ddd = numberOnly.substring(2, 4);
    const firstPart = numberOnly.substring(4, 9);
    const secondPart = numberOnly.substring(9);
    return `(${ddd}) ${firstPart}-${secondPart}`;
  }
  return numberOnly;
};

export const formatMessageTimestamp = (unixTimestamp) => {
  if (!unixTimestamp) return '';
  const date = new Date(unixTimestamp * 1000);
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  return `${hours}:${minutes}`;
};

// 👇 A FUNÇÃO QUE FALTAVA (Adicionada Corretamente)
export const formatTimeShort = (unixTimestamp) => {
  if (!unixTimestamp) return '';
  const date = new Date(unixTimestamp * 1000);
  const now = new Date();

  // Se for hoje, retorna hora:minuto
  if (date.toDateString() === now.toDateString()) {
    return formatMessageTimestamp(unixTimestamp);
  }

  // Se for outro dia, retorna dia/mês
  const day = date.getDate().toString().padStart(2, '0');
  const month = (date.getMonth() + 1).toString().padStart(2, '0');
  return `${day}/${month}`;
};
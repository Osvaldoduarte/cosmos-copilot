// Em frontend/src/utils/formatDisplay.js

export const formatContactName = (name) => {
  // Se 'name' não for uma string ou estiver vazio, retorna um placeholder.
  if (typeof name !== 'string' || !name) {
    return 'Carregando...';
  }

  // Se o nome não contiver '@', significa que já é um nome de contato (ex: "Osvaldo Netto").
  if (!name.includes('@')) {
    return name;
  }

  // Se contiver '@', é um JID (número). Vamos formatá-lo.
  const numberOnly = name.split('@')[0]; // Pega apenas a parte do número, ex: "5541984469423"

  // Verifica se é um número de celular brasileiro padrão (DDI 55 + 11 dígitos)
  if (numberOnly.startsWith('55') && numberOnly.length === 13) {
    const ddd = numberOnly.substring(2, 4); // Pega o DDD, ex: "41"
    const mainNumber = numberOnly.substring(4); // Pega o resto, ex: "984469423"

    // Formata o número principal em dois blocos
    const firstPart = mainNumber.substring(0, 5); // ex: "98446"
    const secondPart = mainNumber.substring(5); // ex: "9423"

    return `${ddd} ${firstPart}-${secondPart}`; // Retorna "41 98446-9423"
  }

  // Se não for um número brasileiro padrão, retorna o número limpo.
  return numberOnly;
};

export const formatMessageTimestamp = (unixTimestamp) => {
  // Se não houver timestamp, retorna uma string vazia.
  if (!unixTimestamp) {
    return '';
  }

  // O timestamp da API vem em segundos, o JavaScript Date() precisa de milissegundos.
  const date = new Date(unixTimestamp * 1000);

  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');

  return `${hours}:${minutes}`;
};
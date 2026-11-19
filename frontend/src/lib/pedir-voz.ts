/**
 * O Nicx responde falando só quando a pessoa pede: digitou, a resposta é
 * texto. Pedir é falar com ele (conversa por voz, "Nicx, ligar") ou escrever
 * algo como "responde falando" ou "lê em voz alta".
 *
 * "Me fala sobre X" não conta: é "me conte", não um pedido de áudio.
 */
const PEDIDOS = [
  // português
  /\bem voz alta\b/,
  /\b(responde|responda|responder|fala|fale|explica|explique|conta|conte)\s+(isso\s+|tudo\s+)?falando\b/,
  /\b(com|por|na) (sua )?voz\b/,
  /\b(le|leia|ler)\s+(isso\s+|essa resposta\s+)?(pra|para) mim\b/,
  /\b(fala|fale|diz|diga)\s+(isso\s+)?(alto|em audio)\b/,
  /\bem audio\b/,
  // inglês
  /\bread (it |this )?(aloud|out loud)\b/,
  /\b(say|speak) (it|this|that)( out)? (aloud|out loud)\b/,
  /\b(out loud|aloud)\b/,
  /\bwith (your )?voice\b/,
  // espanhol / francês
  /\ben voz alta\b/,
  /\ba voix haute\b/,
];

function normalizar(texto: string): string {
  return texto
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^\w\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function pedeVoz(texto: string): boolean {
  const t = normalizar(texto);
  return PEDIDOS.some((r) => r.test(t));
}

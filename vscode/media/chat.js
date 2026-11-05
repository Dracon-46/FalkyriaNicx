// Chat do Nicx no VS Code (webview). Sem bibliotecas: o texto do modelo é
// escapado antes de virar HTML; só blocos de código, `código`, **negrito** e
// quebras de linha ganham formatação.
(function () {
  const vscode = acquireVsCodeApi();
  const T = window.NICX_TEXTOS;
  const conversa = document.getElementById('conversa');
  const campo = document.getElementById('campo');
  const formulario = document.getElementById('formulario');
  const botaoEnviar = document.getElementById('enviar');
  const botaoParar = document.getElementById('parar');
  const respostas = new Map();

  function escapar(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function formatarTexto(s) {
    return escapar(s)
      .replace(/`([^`\n]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>');
  }

  // Texto com blocos ``` -> nós DOM (blocos com Copiar e Inserir).
  function renderizar(alvo, texto) {
    alvo.textContent = '';
    const partes = texto.split(/(```[^\n]*\n[\s\S]*?(?:```|$))/g);
    for (const parte of partes) {
      if (!parte) continue;
      const m = parte.match(/^```([^\n]*)\n([\s\S]*?)(?:```)?$/);
      if (m) {
        const codigo = m[2].replace(/\n$/, '');
        const bloco = document.createElement('div');
        bloco.className = 'bloco';
        const pre = document.createElement('pre');
        const code = document.createElement('code');
        code.textContent = codigo;
        pre.appendChild(code);
        const acoes = document.createElement('div');
        acoes.className = 'acoes';
        for (const [rotulo, tipo] of [[T.copiar, 'copiar'], [T.inserir, 'inserir']]) {
          const b = document.createElement('button');
          b.className = 'secundario';
          b.textContent = rotulo;
          b.addEventListener('click', () => vscode.postMessage({ tipo, codigo }));
          acoes.appendChild(b);
        }
        bloco.appendChild(acoes);
        bloco.appendChild(pre);
        alvo.appendChild(bloco);
      } else {
        const p = document.createElement('div');
        p.className = 'texto';
        p.innerHTML = formatarTexto(parte);
        alvo.appendChild(p);
      }
    }
  }

  function balao(quem, texto) {
    const vazio = conversa.querySelector('.vazio');
    if (vazio) vazio.remove();
    const div = document.createElement('div');
    div.className = 'msg ' + quem;
    if (quem === 'usuario') {
      const rotulo = document.createElement('div');
      rotulo.className = 'quem';
      rotulo.textContent = T.voce;
      div.appendChild(rotulo);
    }
    const corpo = document.createElement('div');
    corpo.className = 'corpo';
    if (texto !== undefined) renderizar(corpo, texto);
    div.appendChild(corpo);
    conversa.appendChild(div);
    conversa.scrollTop = conversa.scrollHeight;
    return corpo;
  }

  function ocupado(sim) {
    botaoParar.hidden = !sim;
    botaoEnviar.disabled = sim;
  }

  window.addEventListener('message', (evento) => {
    const m = evento.data;
    if (m.tipo === 'usuario') {
      balao('usuario', m.texto);
    } else if (m.tipo === 'inicio') {
      const corpo = balao('nicx');
      corpo.innerHTML = '<span class="pensando"></span>';
      corpo.firstChild.textContent = T.pensando;
      respostas.set(m.id, { corpo, texto: '' });
      ocupado(true);
    } else if (m.tipo === 'parte') {
      const r = respostas.get(m.id);
      if (!r) return;
      r.texto += m.texto;
      renderizar(r.corpo, r.texto);
      conversa.scrollTop = conversa.scrollHeight;
    } else if (m.tipo === 'fim' || m.tipo === 'erro') {
      const r = respostas.get(m.id);
      if (r) {
        if (m.tipo === 'erro') {
          r.corpo.textContent = '';
          const e = document.createElement('div');
          e.className = 'erro';
          e.textContent = m.texto;
          r.corpo.appendChild(e);
        } else if (!r.texto) {
          r.corpo.textContent = m.parado ? T.parado : '';
        } else if (m.parado) {
          const p = document.createElement('div');
          p.className = 'nota';
          p.textContent = T.parado;
          r.corpo.appendChild(p);
        }
        respostas.delete(m.id);
      }
      ocupado(false);
    } else if (m.tipo === 'limpar') {
      conversa.innerHTML = '';
      const p = document.createElement('p');
      p.className = 'vazio';
      p.textContent = T.vazio;
      conversa.appendChild(p);
      ocupado(false);
    }
  });

  formulario.addEventListener('submit', (e) => {
    e.preventDefault();
    const texto = campo.value.trim();
    if (!texto || botaoEnviar.disabled) return;
    vscode.postMessage({ tipo: 'enviar', texto });
    campo.value = '';
  });
  campo.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      formulario.requestSubmit();
    }
  });
  botaoParar.addEventListener('click', () => vscode.postMessage({ tipo: 'parar' }));
  document.getElementById('novo').addEventListener('click', () => vscode.postMessage({ tipo: 'novo' }));
  vscode.postMessage({ tipo: 'pronto' });
})();

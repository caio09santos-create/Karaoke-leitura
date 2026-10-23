"""Checagem do microfone (HTML/JS), exibida na barra lateral.

A permissão do microfone vale para a origem do app (localhost), então basta liberar
uma vez aqui: depois os componentes de gravação começam a gravar direto no play,
sem pedir de novo. O botão também mostra o volume captado por alguns segundos,
para conferir que o microfone certo está captando.
"""

HTML_CHECAGEM = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  body { margin: 0; font-family: system-ui, -apple-system, sans-serif; font-size: 13px; }
  #status { color: #444; margin-bottom: 6px; line-height: 1.35; }
  button {
    font-size: 13px; padding: 5px 10px; cursor: pointer;
    border: 1px solid #ccc; border-radius: 6px; background: #fff;
  }
  #rotulo { color: #888; font-size: 11px; margin-top: 8px; }
  #nivel {
    height: 8px; background: #e6e6e6; border-radius: 4px; margin-top: 3px; overflow: hidden;
  }
  #barra { height: 100%; width: 0%; background: #1e9e4a; transition: width .08s; }
</style></head><body>
  <div id="status">Verificando o microfone...</div>
  <button id="testar" type="button">🎤 Testar microfone</button>
  <div id="rotulo">volume captado</div>
  <div id="nivel"><div id="barra"></div></div>
<script>
  const elStatus = document.getElementById("status");
  const elBtn = document.getElementById("testar");
  const elBarra = document.getElementById("barra");

  function mostrar(estado) {
    if (estado === "granted") {
      elStatus.textContent = "✅ Microfone liberado. A gravação começa junto com o play.";
    } else if (estado === "denied") {
      elStatus.textContent = "❌ Microfone bloqueado. Libere no cadeado da barra de endereço.";
    } else {
      elStatus.textContent = "Clique em Testar para liberar o microfone (só precisa uma vez).";
    }
  }

  async function checar() {
    try {
      const p = await navigator.permissions.query({ name: "microphone" });
      mostrar(p.state);
      p.onchange = () => mostrar(p.state);
    } catch (e) {
      mostrar("prompt");  // navegador sem Permissions API
    }
  }

  elBtn.addEventListener("click", async () => {
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      mostrar("denied");
      return;
    }
    elBtn.disabled = true;
    elStatus.textContent = "Fale ou cante algo...";
    const ctx = new AudioContext();
    const analisador = ctx.createAnalyser();
    analisador.fftSize = 1024;
    ctx.createMediaStreamSource(stream).connect(analisador);
    const dados = new Float32Array(analisador.fftSize);
    let pico = 0;
    const fim = performance.now() + 4000;

    function medir() {
      analisador.getFloatTimeDomainData(dados);
      let soma = 0;
      for (const x of dados) soma += x * x;
      const rms = Math.sqrt(soma / dados.length);
      pico = Math.max(pico, rms);
      elBarra.style.width = Math.min(100, rms * 400) + "%";
      if (performance.now() < fim) {
        requestAnimationFrame(medir);
        return;
      }
      stream.getTracks().forEach((t) => t.stop());
      ctx.close();
      elBarra.style.width = "0%";
      elBtn.disabled = false;
      elStatus.textContent = pico > 0.01
        ? "✅ Microfone liberado e captando. Pode cantar!"
        : "⚠️ Liberado, mas não captei som. Confira qual microfone está selecionado.";
    }
    medir();
  });

  checar();
</script></body></html>"""

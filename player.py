"""Player HTML/JS de karaokê: destaca ao vivo a linha atual da letra sincronizada.

O HTML é renderizado no app com `st.components.v1.html` (roda em iframe isolado).
A lógica de tempo é toda client-side (requestAnimationFrame), sem round-trips ao
servidor — o Streamlit rerenderiza de cima a baixo e não atualiza por frame.

Com `audio_data_uri`, embute um <audio> e o realce segue o tempo real da faixa
(`audio.currentTime`); sem áudio, usa um cronômetro manual (▶/⟲).
"""

import json

_BOTOES = (
    '<button id="play" type="button">▶</button>'
    '<button id="reset" type="button">⟲</button>'
)

_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: system-ui, -apple-system, sans-serif; }
  #barra { display: flex; align-items: center; gap: 8px; padding: 6px 4px; }
  #barra button {
    font-size: 16px; padding: 4px 10px; cursor: pointer;
    border: 1px solid #ccc; border-radius: 6px; background: #fff;
  }
  #tempo { font-variant-numeric: tabular-nums; color: #555; min-width: 46px; }
  #atraso { width: 64px; }
  label { font-size: 12px; color: #666; }
  audio { width: 100%; margin: 4px 0; }
  #letras { height: __ALTURA__px; overflow-y: auto; padding: 8px 4px; }
  .linha {
    padding: 4px 6px; color: #9aa0a6; font-size: 16px; line-height: 1.5;
    transition: color .15s, transform .15s;
  }
  .linha.ativa {
    color: #1e9e4a; font-weight: 700; font-size: 19px;
    transform: scale(1.02); transform-origin: left center;
  }
</style></head><body>
  <div id="barra">
    __BOTOES__
    <span id="tempo">0.0s</span>
    <label>atraso (s):
      <input id="atraso" type="number" step="0.5" value="__ATRASO__">
    </label>
  </div>
  __AUDIO_EL__
  <div id="letras"></div>
<script>
  const LINHAS = __DADOS__;
  const USAR_AUDIO = __USAR_AUDIO__;
  let atraso = __ATRASO__;
  let tocando = false, base = 0, decorrido = 0, idxAtual = -1;

  const cont = document.getElementById("letras");
  LINHAS.forEach(([t, txt], i) => {
    const d = document.createElement("div");
    d.className = "linha"; d.dataset.i = i; d.textContent = txt;
    cont.appendChild(d);
  });
  const divs = [...cont.children];
  const elAudio = document.getElementById("audio");
  const elPlay = document.getElementById("play");
  const elReset = document.getElementById("reset");
  const elTempo = document.getElementById("tempo");
  const elAtraso = document.getElementById("atraso");

  if (elAtraso) elAtraso.addEventListener("change", () => {
    atraso = parseFloat(elAtraso.value) || 0;
  });
  if (elPlay) elPlay.addEventListener("click", () => {
    tocando = !tocando;
    elPlay.textContent = tocando ? "⏸" : "▶";
    if (tocando) base = performance.now();
  });
  if (elReset) elReset.addEventListener("click", () => {
    tocando = false; elPlay.textContent = "▶";
    decorrido = 0; idxAtual = -1;
    divs.forEach((d) => d.classList.remove("ativa"));
    cont.scrollTop = 0; elTempo.textContent = "0.0s";
  });

  function acharIdx(seg) {
    let idx = -1;
    for (let i = 0; i < LINHAS.length; i++) {
      if (LINHAS[i][0] <= seg) idx = i; else break;
    }
    return idx;
  }
  function tick() {
    if (USAR_AUDIO && elAudio) {
      decorrido = elAudio.currentTime;
    } else if (tocando) {
      const agora = performance.now();
      decorrido += (agora - base) / 1000;
      base = agora;
    }
    elTempo.textContent = decorrido.toFixed(1) + "s";
    const idx = acharIdx(decorrido - atraso);
    if (idx !== idxAtual) {
      if (idxAtual >= 0 && divs[idxAtual]) divs[idxAtual].classList.remove("ativa");
      if (idx >= 0 && divs[idx]) {
        divs[idx].classList.add("ativa");
        divs[idx].scrollIntoView({ block: "center", behavior: "smooth" });
      }
      idxAtual = idx;
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
</script></body></html>"""


def construir_player_sincronizado(
    synced: list[tuple[float, str]],
    altura: int = 320,
    atraso: float = 0.0,
    audio_data_uri: str | None = None,
) -> str:
    """Monta o HTML/JS autocontido do prompter de karaokê.

    `synced` é uma lista de (tempo_em_segundos, texto). Com `audio_data_uri`, embute
    um <audio> e o realce segue `audio.currentTime`. Sem letra, devolve aviso inócuo.
    """
    if not synced:
        return "<p style='font-family:sans-serif;color:#888'>Sem letra sincronizada.</p>"

    linhas = [[float(t), str(texto)] for t, texto in synced]
    # `</` escapado evita que uma letra com `</script>` feche a tag prematuramente.
    dados = json.dumps(linhas, ensure_ascii=False).replace("</", "<\\/")
    atraso_json = json.dumps(float(atraso))

    if audio_data_uri:
        audio_el = f'<audio id="audio" controls preload="auto" src="{audio_data_uri}"></audio>'
        botoes = ""
        usar_audio = "true"
    else:
        audio_el = ""
        botoes = _BOTOES
        usar_audio = "false"

    return (
        _TEMPLATE.replace("__ALTURA__", str(int(altura)))
        .replace("__DADOS__", dados)
        .replace("__ATRASO__", atraso_json)
        .replace("__USAR_AUDIO__", usar_audio)
        .replace("__BOTOES__", botoes)
        .replace("__AUDIO_EL__", audio_el)
    )

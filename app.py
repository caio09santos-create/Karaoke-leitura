"""Karaokê com nota de leitura da letra.

Execute com:  streamlit run app.py
"""

import base64
import hashlib
import html
import io

import streamlit as st
import streamlit.components.v1 as components
from faster_whisper import WhisperModel

from audio import baixar_audio, extrair_metadados
from avaliacao import avaliar, normalizar_palavra
from gravador import gravar_cantando
from letras import buscar_letra_sincronizada
from player import construir_player_sincronizado

st.set_page_config(page_title="Karaokê - Nota de Leitura", page_icon="🎤")

IDIOMAS = {
    "Detectar automaticamente": None,
    "Português": "pt",
    "Inglês": "en",
    "Espanhol": "es",
}


# ---------- Reconhecimento de voz ----------
@st.cache_resource(show_spinner="Carregando o modelo de voz (na 1ª vez ele é baixado)...")
def carregar_modelo(tamanho: str) -> WhisperModel:
    return WhisperModel(tamanho, device="cpu", compute_type="int8")


def transcrever(
    audio_bytes: bytes, idioma: str | None, tamanho: str
) -> tuple[str, str, list[tuple[str, float]]]:
    """Transcreve o áudio e devolve (texto, idioma, [(palavra, tempo_inicio), ...])."""
    modelo = carregar_modelo(tamanho)
    segmentos, info = modelo.transcribe(
        io.BytesIO(audio_bytes),
        language=idioma,
        vad_filter=True,  # ignora trechos de silêncio
        beam_size=5,
        word_timestamps=True,
    )
    partes: list[str] = []
    palavras_tempos: list[tuple[str, float]] = []
    for seg in segmentos:
        partes.append(seg.text.strip())
        for palavra in seg.words or []:
            palavras_tempos.append((palavra.word, palavra.start))
    return " ".join(partes), info.language, palavras_tempos


# ---------- Callbacks ----------
def acao_buscar_letra():
    artista = st.session_state.get("artista", "").strip()
    titulo = st.session_state.get("titulo", "").strip()
    if not artista or not titulo:
        st.session_state["aviso"] = "Preencha artista e título."
        return
    dados = buscar_letra_cache(artista, titulo)
    if dados:
        st.session_state["letra"] = dados["plain"]
        st.session_state["synced"] = dados["synced"]
        st.session_state["aviso"] = None
    else:
        st.session_state["synced"] = None
        st.session_state["aviso"] = "Letra não encontrada. Cole a letra manualmente abaixo."


# ---------- Exibição ----------
def mostrar_feedback_por_linha(por_linha):
    """Exibe cada linha com % de acerto e palavras certas (verde) / erradas (vermelho)."""
    blocos = []
    for item in por_linha:
        palavras_html = " ".join(
            f'<span style="color:{"#1e9e4a" if acertou else "#d63333"};'
            f'font-weight:600">{html.escape(palavra)}</span>'
            for palavra, acertou in item["palavras"]
        )
        pct = round(item["taxa"] * 100)
        blocos.append(
            '<div style="margin-bottom:4px">'
            f'<span style="color:#888;font-size:0.8em">{pct:>3}%</span>&nbsp; {palavras_html}'
            "</div>"
        )
    st.markdown(
        f'<div style="line-height:1.8">{"".join(blocos)}</div>', unsafe_allow_html=True
    )


@st.cache_data(show_spinner="Baixando o áudio do link...")
def carregar_audio(url: str) -> tuple[bytes, str] | None:
    """Baixa o áudio da URL (cacheado por URL). (bytes, mimetype) ou None."""
    return baixar_audio(url)


@st.cache_data(show_spinner="Lendo dados do vídeo...")
def carregar_metadados(url: str) -> dict | None:
    """Lê artista/título do vídeo (cacheado por URL)."""
    return extrair_metadados(url)


@st.cache_data(show_spinner=False)
def buscar_letra_cache(artista: str, titulo: str) -> dict | None:
    """Busca a letra no LRCLIB (cacheada por artista+título)."""
    return buscar_letra_sincronizada(artista, titulo)


def _data_uri(dados: bytes, mimetype: str) -> str:
    b64 = base64.b64encode(dados).decode("ascii")
    return f"data:{mimetype};base64,{b64}"


def _chave_linha(texto: str) -> str:
    """Normaliza uma linha para casar letra digitada com a letra sincronizada."""
    return " ".join(filter(None, (normalizar_palavra(p) for p in texto.split())))


def _mmss(segundos: float) -> str:
    total = int(round(segundos))
    return f"{total // 60:02d}:{total % 60:02d}"


def montar_timeline(por_linha, synced) -> list[dict]:
    """Casa cada linha cantada (com tempo) ao tempo de referência do LRC."""
    ref_por_chave: dict[str, float] = {}
    for tempo, texto in synced:
        ref_por_chave.setdefault(_chave_linha(texto), tempo)
    pontos = []
    for item in por_linha:
        if item["tempo_cantado"] is None:
            continue
        referencia = ref_por_chave.get(_chave_linha(item["texto"]))
        if referencia is not None:
            pontos.append(
                {
                    "texto": item["texto"],
                    "referencia": referencia,
                    "cantado": item["tempo_cantado"],
                }
            )
    pontos.sort(key=lambda p: p["referencia"])
    return pontos


def mostrar_timeline(pontos):
    st.markdown(
        "**Linha do tempo (informativo)** — quando você cantou cada trecho "
        "comparado à referência da música:"
    )
    tabela = [
        {"Trecho": p["texto"], "Referência": _mmss(p["referencia"]), "Você": _mmss(p["cantado"])}
        for p in pontos
    ]
    st.dataframe(tabela, hide_index=True, width="stretch")

    # Tempos relativos ao início de cada série, para comparar o ritmo.
    base_ref = pontos[0]["referencia"]
    base_voce = pontos[0]["cantado"]
    st.line_chart(
        {
            "Referência (rel. s)": [p["referencia"] - base_ref for p in pontos],
            "Você (rel. s)": [p["cantado"] - base_voce for p in pontos],
        }
    )
    st.caption(
        "Tempos relativos ao 1º trecho (sua gravação e a música não partem do "
        "mesmo relógio). Linhas próximas = ritmo parecido."
    )


# ---------- Interface ----------
st.title("🎤 Karaokê - Nota de Leitura")
st.caption("Cante acompanhando a letra e receba uma nota pelo quanto você acertou.")

with st.sidebar:
    st.header("Configurações")
    idioma_nome = st.selectbox("Idioma da música", list(IDIOMAS))
    tamanho_modelo = st.selectbox(
        "Precisão do reconhecimento",
        ["small", "medium", "base"],
        help="small: equilíbrio. medium: mais preciso e mais lento. base: mais rápido.",
    )

# 1. Música
st.subheader("1. Escolha a música")
url = st.text_input("Link do YouTube (de preferência uma versão karaokê/instrumental)")
if url:
    st.video(url)
if url and url != st.session_state.get("url_processada"):
    st.session_state["url_processada"] = url
    # limpa o estado do link anterior (evita letra/áudio/nota "grudados")
    for _k in ("artista", "titulo", "letra"):
        st.session_state[_k] = ""
    st.session_state["synced"] = None
    st.session_state["audio_musica"] = None
    for _k in ("chave_transcricao", "transcricao", "tempos", "idioma_det"):
        st.session_state.pop(_k, None)
    with st.spinner("Carregando o vídeo: áudio, artista/título e letra..."):
        meta = carregar_metadados(url)
        if meta:
            st.session_state["artista"] = meta["artista"]
            st.session_state["titulo"] = meta["titulo"]
        else:
            st.info("Não consegui ler artista/título do vídeo — preencha abaixo.")

        st.session_state["audio_musica"] = carregar_audio(url)
        if not st.session_state["audio_musica"]:
            st.warning("Não consegui baixar o áudio (letra e nota continuam funcionando).")

        if meta:
            dados = buscar_letra_cache(meta["artista"], meta["titulo"])
            if dados:
                st.session_state["letra"] = dados["plain"]
                st.session_state["synced"] = dados["synced"]
            else:
                st.info("Letra não encontrada automaticamente — ajuste os campos e busque abaixo.")

audio_musica = st.session_state.get("audio_musica")
if audio_musica:
    st.audio(audio_musica[0], format=audio_musica[1])
    st.caption(
        "Áudio para uso pessoal/estudo. Dê play na Prévia sincronizada para a letra "
        "acompanhar. (webm/opus pode não tocar no Safari; prefira links com m4a.)"
    )

# 2. Letra
st.subheader("2. Letra")
col1, col2 = st.columns(2)
col1.text_input("Artista", key="artista")
col2.text_input("Título", key="titulo")
st.button("Buscar letra", on_click=acao_buscar_letra)
if st.session_state.get("aviso"):
    st.warning(st.session_state["aviso"])
letra = st.text_area("Letra (você pode colar ou editar)", key="letra", height=250)
synced_atual = st.session_state.get("synced")
if synced_atual and not audio_musica:
    st.caption(
        "✨ Letra sincronizada encontrada — feedback por linha e linha do tempo no resultado."
    )
    with st.expander("🎤 Prévia sincronizada (cante junto)", expanded=True):
        st.caption(
            "Clique ▶ (relógio manual) — a letra destaca a linha atual; 'atraso (s)' alinha. "
            "Carregue o áudio acima para tocar e gravar juntos na etapa 3."
        )
        components.html(construir_player_sincronizado(synced_atual), height=400)
elif synced_atual:
    st.caption("✨ Letra sincronizada — na etapa 3 a base toca e grava junto, com realce ao vivo.")

# 3. Gravação
st.subheader("3. Cante!")
usar_gravador = bool(synced_atual and audio_musica)
gravacao = None
if usar_gravador:
    st.caption(
        "Toque a base e clique **🎯 Alinhar 1ª linha** quando a 1ª linha começar (afine com "
        "−/+). Depois **▶ Iniciar**: a base toca e o microfone grava juntos; **⏹ Parar** ao "
        "terminar. Use fones de ouvido."
    )
    # key por música: troca de link remonta o componente com a base/letra novas
    gravacao = gravar_cantando(
        synced_atual,
        audio_data_uri=_data_uri(*audio_musica),
        key="grav_" + hashlib.sha1(url.encode()).hexdigest()[:8],
    )
    audio_bytes = gravacao[0] if gravacao else None
else:
    st.info(
        "Use fones de ouvido: se o microfone captar a música, "
        "a voz do cantor original conta como sua."
    )
    audio = st.audio_input("Clique para gravar e clique de novo para parar")
    audio_bytes = audio.getvalue() if audio else None

# 4. Nota (calculada automaticamente quando há gravação)
st.subheader("4. Resultado")
if not audio_bytes:
    st.caption("Grave a sua voz na etapa 3 — a nota aparece aqui automaticamente.")
elif not letra.strip():
    st.warning("Preencha a letra para calcular a nota.")
else:
    # Transcreve só quando a gravação (ou o modelo/idioma) muda; avaliar é barato.
    chave = f"{hashlib.sha1(audio_bytes).hexdigest()}|{tamanho_modelo}|{idioma_nome}"
    if st.session_state.get("chave_transcricao") != chave:
        st.session_state["chave_transcricao"] = chave
        with st.spinner("Ouvindo sua apresentação..."):
            transcricao, idioma_det, tempos = transcrever(
                audio_bytes, IDIOMAS[idioma_nome], tamanho_modelo
            )
        st.session_state["transcricao"] = transcricao
        st.session_state["idioma_det"] = idioma_det
        st.session_state["tempos"] = tempos

    transcricao = st.session_state.get("transcricao", "")
    if not transcricao.strip():
        st.error("Não consegui ouvir nada. Verifique o microfone e tente de novo.")
    else:
        resultado = avaliar(letra, transcricao, hipotese_tempos=st.session_state.get("tempos"))
        c1, c2 = st.columns(2)
        c1.metric("Nota", f"{resultado['nota']}/100")
        c2.metric("Palavras certas", f"{resultado['acertos']} de {resultado['total']}")

        if resultado["nota"] >= 90:
            st.success("Show! Você é a estrela da noite! 🌟")
        elif resultado["nota"] >= 60:
            st.info("Mandou bem! Dá pra melhorar mais um pouco. 🎶")
        else:
            st.warning("Continue treinando! 💪")

        st.markdown("**Seu desempenho na letra:**")
        mostrar_feedback_por_linha(resultado["por_linha"])

        synced = st.session_state.get("synced")
        pontos = montar_timeline(resultado["por_linha"], synced) if synced else []
        if pontos:
            mostrar_timeline(pontos)

        with st.expander("Ver o que o app entendeu"):
            st.write(f"Idioma detectado: `{st.session_state.get('idioma_det')}`")
            st.write(transcricao)

"""Karaokê com nota de leitura da letra.

Execute com:  streamlit run app.py
"""

import html
import io

import streamlit as st
from faster_whisper import WhisperModel

from avaliacao import avaliar
from letras import buscar_letra

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


def transcrever(audio_bytes: bytes, idioma: str | None, tamanho: str) -> tuple[str, str]:
    modelo = carregar_modelo(tamanho)
    segmentos, info = modelo.transcribe(
        io.BytesIO(audio_bytes),
        language=idioma,
        vad_filter=True,  # ignora trechos de silêncio
        beam_size=5,
    )
    texto = " ".join(seg.text.strip() for seg in segmentos)
    return texto, info.language


# ---------- Callbacks ----------
def acao_buscar_letra():
    artista = st.session_state.get("artista", "").strip()
    titulo = st.session_state.get("titulo", "").strip()
    if not artista or not titulo:
        st.session_state["aviso"] = "Preencha artista e título."
        return
    letra = buscar_letra(artista, titulo)
    if letra:
        st.session_state["letra"] = letra
        st.session_state["aviso"] = None
    else:
        st.session_state["aviso"] = "Letra não encontrada. Cole a letra manualmente abaixo."


def mostrar_feedback(palavras):
    """Exibe a letra com palavras certas em verde e erradas em vermelho."""
    linhas: dict[int, list[str]] = {}
    for n_linha, palavra, acertou in palavras:
        cor = "#1e9e4a" if acertou else "#d63333"
        linhas.setdefault(n_linha, []).append(
            f'<span style="color:{cor};font-weight:600">{html.escape(palavra)}</span>'
        )
    corpo = "<br>".join(" ".join(p) for _, p in sorted(linhas.items()))
    st.markdown(f'<div style="line-height:1.8">{corpo}</div>', unsafe_allow_html=True)


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

# 2. Letra
st.subheader("2. Letra")
col1, col2 = st.columns(2)
col1.text_input("Artista", key="artista")
col2.text_input("Título", key="titulo")
st.button("Buscar letra", on_click=acao_buscar_letra)
if st.session_state.get("aviso"):
    st.warning(st.session_state["aviso"])
letra = st.text_area("Letra (você pode colar ou editar)", key="letra", height=250)

# 3. Gravação
st.subheader("3. Cante!")
st.info(
    "Use fones de ouvido: se o microfone captar a música, "
    "a voz do cantor original conta como sua."
)
audio = st.audio_input("Clique para gravar e clique de novo para parar")

# 4. Nota
st.subheader("4. Resultado")
if st.button("Calcular nota", type="primary", disabled=not (audio and letra.strip())):
    with st.spinner("Ouvindo sua apresentação..."):
        transcricao, idioma_detectado = transcrever(
            audio.getvalue(), IDIOMAS[idioma_nome], tamanho_modelo
        )

    if not transcricao.strip():
        st.error("Não consegui ouvir nada. Verifique o microfone e tente de novo.")
    else:
        resultado = avaliar(letra, transcricao)
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
        mostrar_feedback(resultado["palavras"])

        with st.expander("Ver o que o app entendeu"):
            st.write(f"Idioma detectado: `{idioma_detectado}`")
            st.write(transcricao)

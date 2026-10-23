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

import historico
from afinacao import avaliar_afinacao
from audio import baixar_audio, extrair_metadados, termo_karaoke, youtube_id
from avaliacao import avaliar, normalizar_palavra
from gravador import gravar_cantando, gravar_com_video
from letras import buscar_letra_sincronizada
from microfone import HTML_CHECAGEM
from player import construir_player_sincronizado

st.set_page_config(
    page_title="Karaokê - Nota de Leitura",
    page_icon="🎤",
    layout="centered" if st.session_state.get("modo_dev") else "wide",
)

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
        st.session_state["artista"] = dados.get("artista") or artista
        st.session_state["titulo"] = dados.get("titulo") or titulo
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


@st.cache_data(show_spinner="Buscando no YouTube...")
def buscar_youtube(termo: str) -> list[dict]:
    """Busca versões karaokê no YouTube (import preguiçoso). [] se indisponível."""
    try:
        from youtube_search import YoutubeSearch
    except ImportError:
        return []
    try:
        return YoutubeSearch(termo_karaoke(termo), max_results=6).to_dict()
    except Exception:
        return []


def _url_do_resultado(video: dict) -> str:
    """Monta a URL do YouTube a partir de um resultado da busca."""
    sufixo = video.get("url_suffix")
    if sufixo:
        return "https://www.youtube.com" + sufixo
    vid = video.get("id")
    return f"https://youtu.be/{vid}" if vid else ""


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
        "**Linha do tempo (informativo)** - quando você cantou cada trecho "
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


def _linha_placar(r: dict) -> dict:
    """Formata um registro do histórico para exibição em tabela (Média primeiro)."""
    return {
        "Cantor": r["cantor"],
        "Música": f"{r.get('artista') or '?'} - {r.get('titulo') or '?'}",
        "Média": round(r["media"]),
        "Leitura": r["nota_leitura"],
        "Afinação": r["afinacao"] if r["afinacao"] is not None else "-",
        "Quando": r["data"].replace("T", " "),
    }


def _texto_tendencia(cents: float | None) -> str:
    """Traduz a tendência de afinação (cents assinado) em texto."""
    if cents is None:
        return "sem dados"
    if abs(cents) <= 10:
        return "bem no tom"
    nivel = "um pouco " if abs(cents) <= 25 else ""
    return f"{nivel}{'acima (agudo)' if cents > 0 else 'abaixo (grave)'}"


def _mostrar_resultado_usuario(res: dict):
    """Mostra a nota final grande, mensagem comemorativa e o ranking."""
    final = res["final"]
    af_txt = res["afinacao"] if res["afinacao"] is not None else "-"
    st.markdown(
        "<style>@keyframes surgir {0% {transform: scale(.4); opacity: 0}"
        " 70% {transform: scale(1.08); opacity: 1} 100% {transform: scale(1)}}</style>"
        "<div style='text-align:center;margin:8px 0 18px'>"
        "<div style='font-size:30px;color:#666'>Sua nota</div>"
        "<div style='font-size:200px;font-weight:800;color:#1e9e4a;line-height:1;"
        f"animation:surgir .7s ease-out'>{final}</div>"
        f"<div style='font-size:20px;color:#888'>leitura {res['leitura']}"
        f" · afinação {af_txt}</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    if final >= 85:
        st.balloons()
    if final >= 90:
        st.success("Você é a estrela da noite! 🌟")
    elif final >= 60:
        st.success("Mandou muito bem! 🎶")
    else:
        st.info("Continue treinando! 💪")
    st.markdown("### 🏆 Ranking")
    _mostrar_ranking()


def _mostrar_ranking():
    """Tabela do placar (posição, cantor, música e notas)."""
    rank = historico.ranking()
    if not rank:
        st.caption("Ainda não há apresentações. Cante para aparecer aqui!")
        return
    st.dataframe(
        [{"#": f"{i}º", **_linha_placar(r)} for i, r in enumerate(rank, 1)],
        hide_index=True,
        width="stretch",
    )


@st.dialog("🏆 Ranking", width="large")
def dialog_ranking():
    _mostrar_ranking()


def _contagem(n: int | None) -> str:
    """Formata números grandes de forma curta (ex.: 1,2 mi, 35 mil)."""
    if not n:
        return ""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} mi".replace(".", ",")
    if n >= 1_000:
        return f"{n // 1_000} mil"
    return str(n)


def _mostrar_info_video(meta: dict | None, artista: str, titulo: str):
    """Nome e metadados do vídeo, exibidos embaixo dele."""
    meta = meta or {}
    st.subheader(meta.get("video") or f"{artista} - {titulo}")
    detalhes = []
    if artista or titulo:
        detalhes.append(f"🎵 {artista} - {titulo}")
    if meta.get("canal"):
        detalhes.append(f"📺 {meta['canal']}")
    if meta.get("duracao"):
        detalhes.append(f"⏱️ {_mmss(meta['duracao'])}")
    if meta.get("visualizacoes"):
        detalhes.append(f"👁️ {_contagem(meta['visualizacoes'])} visualizações")
    if detalhes:
        st.caption("  ·  ".join(detalhes))


def tela_usuario(barra):
    """Tela simplificada: entradas na barra lateral; no painel, o vídeo e depois a nota."""
    with barra:
        st.subheader("🎤 Sua vez")
        nome = st.text_input("Seu nome", key="cantor", placeholder="Convidado")
        consulta = st.text_input(
            "Qual música você quer cantar?", placeholder="Ex: Adele Hello"
        ).strip()
        url = ""
        if consulta:
            if youtube_id(consulta):
                url = consulta
            else:
                resultados = buscar_youtube(consulta)
                if resultados:
                    rotulos = {"(selecione uma versão)": ""}
                    for v in resultados:
                        rotulo = "🎵 {} ({}) - {}".format(
                            v.get("title", "?"), v.get("duration", "?"), v.get("channel", "?")
                        )
                        rotulos[rotulo] = _url_do_resultado(v)
                    url = rotulos[st.selectbox("Escolha a versão:", list(rotulos))]
                else:
                    st.warning("Nada encontrado. Tente outro termo ou cole um link do YouTube.")
        if st.button("🏆 Ver ranking", width="stretch"):
            dialog_ranking()

    vid = youtube_id(url) if url else None
    if not vid:
        st.title("🎤 Karaokê")
        st.markdown(
            "Busque uma música na barra lateral, dê play no vídeo e cante. "
            "A sua nota aparece no final."
        )
        return

    # trocar de vídeo reinicia o fluxo
    if st.session_state.get("vid_user") != vid:
        st.session_state["vid_user"] = vid
        st.session_state["fase_user"] = "cantando"
        st.session_state["tentativa_user"] = st.session_state.get("tentativa_user", 0) + 1
        st.session_state.pop("audio_user", None)
        st.session_state.pop("resultado_user", None)

    # letra por baixo dos panos (necessária para a nota de leitura)
    meta = carregar_metadados(url)
    dados = buscar_letra_cache(meta["artista"], meta["titulo"]) if meta else None
    artista = (dados or {}).get("artista") or (meta["artista"] if meta else "")
    titulo = (dados or {}).get("titulo") or (meta["titulo"] if meta else "")
    if not dados:
        _mostrar_info_video(meta, artista, titulo)
        st.warning("Não encontrei a letra dessa versão. Tente outra versão da música.")
        return
    letra = dados["plain"]

    fase = st.session_state.get("fase_user", "cantando")
    tentativa = st.session_state.get("tentativa_user", 0)

    if fase == "resultado":
        _mostrar_resultado_usuario(st.session_state["resultado_user"])
        if st.button("🔁 Cantar de novo"):
            st.session_state["fase_user"] = "cantando"
            st.session_state["tentativa_user"] = tentativa + 1
            st.session_state.pop("audio_user", None)
            st.session_state.pop("resultado_user", None)
            st.rerun()
        return

    if fase == "calculando":
        # o vídeo segue montado (mesma chave): o componente mostra os números
        # rodando por cima dele enquanto a nota é calculada aqui
        gravar_com_video(vid, key=f"user_{vid}_{tentativa}", sobrepor=True)
        _mostrar_info_video(meta, artista, titulo)
        audio_bytes = st.session_state.get("audio_user")
        transcricao, _, tempos = transcrever(audio_bytes, None, "small")
        afin = avaliar_afinacao(audio_bytes)
        leitura = (
            avaliar(letra, transcricao, hipotese_tempos=tempos) if transcricao.strip() else None
        )
        af_nota = afin["nota"] if afin else None
        leitura_nota = leitura["nota"] if leitura else 0
        final = historico.media_pontos(leitura_nota, af_nota)
        historico.salvar(
            nome or "Convidado",
            artista,
            titulo,
            leitura_nota,
            af_nota,
            leitura["acertos"] if leitura else 0,
            leitura["total"] if leitura else 0,
        )
        st.session_state["resultado_user"] = {
            "final": final,
            "leitura": leitura_nota,
            "afinacao": af_nota,
        }
        st.session_state["fase_user"] = "resultado"
        st.rerun()

    # fase "cantando": o vídeo no topo do painel, nome e metadados embaixo dele
    gravacao = gravar_com_video(vid, key=f"user_{vid}_{tentativa}", sobrepor=True)
    _mostrar_info_video(meta, artista, titulo)
    st.caption("Ao pausar ou terminar o vídeo, sua nota aparece. Use fones de ouvido.")
    if gravacao:
        st.session_state["audio_user"] = gravacao[0]
        st.session_state["fase_user"] = "calculando"
        st.rerun()


# ---------- Interface ----------
# A barra lateral tem duas áreas: o conteúdo em cima e o rodapé com o toggle do modo
# desenvolvedor. O toggle é lido primeiro (decide a tela), mas aparece por último.
barra_conteudo = st.sidebar.container()
barra_rodape = st.sidebar.container()
with barra_rodape:
    st.divider()
    modo_dev = st.toggle("🛠️ Modo desenvolvedor", value=False, key="modo_dev")

with barra_conteudo:
    st.subheader("🎚️ Preparação")
    st.caption("Libere e teste o microfone uma vez; depois é só dar play e cantar.")
    components.html(HTML_CHECAGEM, height=125)

if not modo_dev:
    tela_usuario(barra_conteudo)
    st.stop()

# ----- Modo desenvolvedor (tela completa) -----
st.title("🎤 Karaokê - Nota de Leitura")
st.caption("Cante acompanhando a letra e receba uma nota pelo quanto você acertou.")

with barra_conteudo:
    st.header("Configurações")
    st.text_input("Seu nome", key="cantor", placeholder="Convidado")
    idioma_nome = st.selectbox("Idioma da música", list(IDIOMAS))
    tamanho_modelo = st.selectbox(
        "Precisão do reconhecimento",
        ["small", "medium", "base"],
        help="small: equilíbrio. medium: mais preciso e mais lento. base: mais rápido.",
    )

# 1. Música
st.subheader("1. Escolha a música")
consulta = st.text_input(
    "Pesquise a música/artista ou cole um link do YouTube",
    placeholder="Ex: Adele Hello",
).strip()
url = ""
if consulta:
    if youtube_id(consulta):
        url = consulta  # colou um link direto
    else:
        resultados = buscar_youtube(consulta)
        if resultados:
            rotulos = {"(selecione uma versão)": ""}
            for v in resultados:
                rotulo = "🎵 {} ({}) - {}".format(
                    v.get("title", "?"), v.get("duration", "?"), v.get("channel", "?")
                )
                rotulos[rotulo] = _url_do_resultado(v)
            escolha = st.selectbox("Resultados encontrados:", list(rotulos))
            url = rotulos[escolha]
        else:
            st.warning(
                "Nada encontrado (ou a busca está indisponível). "
                "Você também pode colar um link do YouTube acima."
            )

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
            st.info("Não consegui ler artista/título do vídeo - preencha abaixo.")

        st.session_state["audio_musica"] = carregar_audio(url)
        if not st.session_state["audio_musica"]:
            st.warning("Não consegui baixar o áudio (letra e nota continuam funcionando).")

        if meta:
            dados = buscar_letra_cache(meta["artista"], meta["titulo"])
            if dados:
                st.session_state["letra"] = dados["plain"]
                st.session_state["synced"] = dados["synced"]
                # nomes canônicos do LRCLIB corrigem palpites trocados do título
                st.session_state["artista"] = dados.get("artista") or meta["artista"]
                st.session_state["titulo"] = dados.get("titulo") or meta["titulo"]
            else:
                st.info("Letra não encontrada automaticamente - ajuste os campos e busque abaixo.")

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
        "✨ Letra sincronizada encontrada - feedback por linha e linha do tempo no resultado."
    )
    with st.expander("🎤 Prévia sincronizada (cante junto)", expanded=True):
        st.caption(
            "Clique ▶ (relógio manual) - a letra destaca a linha atual; 'atraso (s)' alinha. "
            "Carregue o áudio acima para tocar e gravar juntos na etapa 3."
        )
        components.html(construir_player_sincronizado(synced_atual), height=400)
elif synced_atual:
    st.caption("✨ Letra sincronizada - na etapa 3 a base toca e grava junto, com realce ao vivo.")

# 3. Gravação
st.subheader("3. Cante!")
audio_bytes = None
vid = youtube_id(url) if url else None
chave_musica = hashlib.sha1(url.encode()).hexdigest()[:8] if url else "x"
modo_base_ok = bool(synced_atual and audio_musica)  # tocar a base aqui + realce

if modo_base_ok or vid:
    opcoes = []
    if modo_base_ok:
        opcoes.append("🎧 Tocar a base aqui e acompanhar a letra")
    if vid:
        opcoes.append("🎬 Cantar com o vídeo do YouTube")
    modo = st.radio("Como você quer cantar?", opcoes, horizontal=True)

    if modo.startswith("🎬"):
        st.caption(
            "Dê **play no vídeo** (a letra aparece nele) e cante: a gravação começa junto. "
            "Ao **pausar ou terminar** o vídeo, a nota é calculada. Use fones de ouvido "
            "e, de preferência, um vídeo karaokê/instrumental."
        )
        gravacao = gravar_com_video(vid, key="ytg_" + chave_musica)
        audio_bytes = gravacao[0] if gravacao else None
    else:
        st.caption(
            "Toque a base e clique **🎯 Alinhar 1ª linha** quando a 1ª linha começar (afine com "
            "-/+). Depois **▶ Iniciar**: a base toca e o microfone grava juntos; **⏹ Parar** ao "
            "terminar. Use fones de ouvido."
        )
        # key por música: troca de link remonta o componente com a base/letra novas
        gravacao = gravar_cantando(
            synced_atual, audio_data_uri=_data_uri(*audio_musica), key="grav_" + chave_musica
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
    st.caption("Grave a sua voz na etapa 3 - a nota aparece aqui automaticamente.")
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
            afinacao = avaliar_afinacao(audio_bytes)
        st.session_state["transcricao"] = transcricao
        st.session_state["idioma_det"] = idioma_det
        st.session_state["tempos"] = tempos
        st.session_state["afinacao"] = afinacao

    transcricao = st.session_state.get("transcricao", "")
    if not transcricao.strip():
        st.error("Não consegui ouvir nada. Verifique o microfone e tente de novo.")
    else:
        resultado = avaliar(letra, transcricao, hipotese_tempos=st.session_state.get("tempos"))
        afinacao = st.session_state.get("afinacao")

        # salva no histórico uma única vez por gravação
        if st.session_state.get("chave_salva") != chave:
            st.session_state["chave_salva"] = chave
            historico.salvar(
                st.session_state.get("cantor") or "Convidado",
                st.session_state.get("artista", ""),
                st.session_state.get("titulo", ""),
                resultado["nota"],
                afinacao["nota"] if afinacao else None,
                resultado["acertos"],
                resultado["total"],
            )

        c1, c2, c3 = st.columns(3)
        c1.metric("Nota (leitura)", f"{resultado['nota']}/100")
        c2.metric("Palavras certas", f"{resultado['acertos']} de {resultado['total']}")
        c3.metric("Afinação", f"{afinacao['nota']}/100" if afinacao else "-")
        if afinacao:
            pct = round(afinacao["pct_afinado"] * 100)
            tend = _texto_tendencia(afinacao["tendencia"])
            st.caption(
                "Afinação = quão centrado nas notas (intonação), não a melodia exata. "
                f"Afinado em {pct}% do tempo; tendência: {tend}. "
                "Use fones de ouvido para uma medição melhor."
            )
            serie = afinacao.get("serie")
            if serie:
                with st.expander("Ver afinação ao longo do tempo"):
                    st.caption(
                        "Sua nota (linha) comparada à nota alvo, em semitons. "
                        "Quanto mais próximas, mais afinado."
                    )
                    st.line_chart(serie)

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

# 5. Histórico e placar
st.subheader("📊 Histórico e placar")
_rank = historico.ranking()
if _rank:
    st.markdown("**🏆 Placar - por média de leitura + afinação**")
    st.dataframe(
        [{"#": f"{i}º", **_linha_placar(r)} for i, r in enumerate(_rank, 1)],
        hide_index=True,
        width="stretch",
    )
    st.markdown("**🕒 Apresentações recentes**")
    st.dataframe(
        [_linha_placar(r) for r in historico.recentes()], hide_index=True, width="stretch"
    )
else:
    st.caption("Ainda não há apresentações registradas. Cante para aparecer aqui!")

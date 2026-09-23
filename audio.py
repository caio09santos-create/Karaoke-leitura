"""Baixa o áudio de um link (YouTube etc.) com yt-dlp, em formato tocável no navegador.

O `import yt_dlp` é preguiçoso (dentro de `baixar_audio`) para o módulo poder ser
importado — e testado — sem o pacote instalado. Escolhemos um formato de áudio já
tocável em `<audio>` (m4a/webm), evitando conversão via ffmpeg.
"""

import glob
import os
import re
import tempfile

_MIMETYPES = {
    "m4a": "audio/mp4",
    "mp4": "audio/mp4",
    "webm": "audio/webm",
    "opus": "audio/ogg",
    "ogg": "audio/ogg",
    "mp3": "audio/mpeg",
}


def _mimetype_por_ext(ext: str) -> str:
    """'m4a' / '.m4a' -> 'audio/mp4'; desconhecido -> 'audio/mpeg'."""
    return _MIMETYPES.get(ext.lower().lstrip("."), "audio/mpeg")


def _opcoes_ydl(pasta: str) -> dict:
    """Opções do yt-dlp: melhor áudio tocável no navegador, sem playlist, silencioso."""
    return {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "outtmpl": os.path.join(pasta, "audio.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }


# Marcadores comuns de título do YouTube que não fazem parte do nome da música.
_LIXO_TITULO = re.compile(
    r"\s*[\(\[]\s*(?:official|lyric|lyrics|audio|video|music|clipe|v[ií]deo|"
    r"visualizer|hd|4k|mv|ao vivo|live|legendado|karaok|playback|instrumental|cover)"
    r"[^\)\]]*[\)\]]",
    re.IGNORECASE,
)
_EH_KARAOKE = re.compile(r"karaok|playback|instrumental", re.IGNORECASE)


def _limpar_titulo(titulo: str) -> str:
    """Corta texto promocional após '|', remove '(Official Video)'/'(Karaokê)' e pontuação."""
    titulo = titulo.split("|")[0]
    return _LIXO_TITULO.sub("", titulo).strip(" -–—\"'")


def _parsear_artista_titulo(info: dict) -> tuple[str, str]:
    """Best-effort: usa artist/track (YouTube Music) ou infere de title/uploader.

    Em títulos de karaokê/playback o formato costuma ser "Música - Artista"
    (invertido do usual), então detectamos e trocamos a ordem.
    """
    artista = (info.get("artist") or info.get("creator") or "").strip()
    faixa = (info.get("track") or "").strip()
    if artista and faixa:
        return artista, _limpar_titulo(faixa)

    titulo_bruto = (info.get("title") or "").strip()
    eh_karaoke = bool(_EH_KARAOKE.search(titulo_bruto))
    if " - " in titulo_bruto:
        esq, dir_ = (p.strip() for p in titulo_bruto.split(" - ", 1))
        if eh_karaoke:  # "Música (Karaokê) - Artista"
            return _limpar_titulo(dir_), _limpar_titulo(esq)
        return _limpar_titulo(esq), _limpar_titulo(dir_)

    canal = (info.get("uploader") or info.get("channel") or "").strip()
    canal = re.sub(r"\s*-\s*Topic$", "", canal)  # canais auto do YT Music
    canal = re.sub(r"\bkaraok\w*\b|\bplayback\b", "", canal, flags=re.IGNORECASE)
    return canal.strip(" -"), _limpar_titulo(titulo_bruto)


def extrair_metadados(url: str) -> dict | None:
    """Lê os metadados do vídeo (sem baixar). Retorna {'artista', 'titulo'} ou None."""
    try:
        import yt_dlp
    except ImportError:
        return None
    try:
        opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return None
    if not info:
        return None
    artista, titulo = _parsear_artista_titulo(info)
    if not titulo:
        return None
    return {"artista": artista, "titulo": titulo}


def baixar_audio(url: str) -> tuple[bytes, str] | None:
    """Baixa o áudio da URL. Retorna (bytes, mimetype) ou None em caso de falha."""
    try:
        import yt_dlp
    except ImportError:
        return None

    with tempfile.TemporaryDirectory() as pasta:
        try:
            with yt_dlp.YoutubeDL(_opcoes_ydl(pasta)) as ydl:
                ydl.download([url])
        except Exception:
            return None

        arquivos = sorted(glob.glob(os.path.join(pasta, "audio.*")))
        if not arquivos:
            return None
        caminho = arquivos[0]
        with open(caminho, "rb") as arquivo:
            dados = arquivo.read()
        return dados, _mimetype_por_ext(os.path.splitext(caminho)[1])

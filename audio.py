"""Baixa o áudio de um link (YouTube etc.) com yt-dlp, em formato tocável no navegador.

O `import yt_dlp` é preguiçoso (dentro de `baixar_audio`) para o módulo poder ser
importado — e testado — sem o pacote instalado. Escolhemos um formato de áudio já
tocável em `<audio>` (m4a/webm), evitando conversão via ffmpeg.
"""

import glob
import os
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

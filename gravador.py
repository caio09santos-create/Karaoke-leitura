"""Componente Streamlit bidirecional: toca a base e grava o microfone em um clique.

`declare_component` é preguiçoso para o módulo (e o helper puro `_decode_gravacao`)
poderem ser importados/testados sem o streamlit instalado (ex.: no CI).
"""

import base64
import os

_BASE = os.path.dirname(os.path.abspath(__file__))
_componentes: dict[str, object] = {}


def _get_componente(nome: str):
    """Declara (uma vez) o componente cujos arquivos estão em ./<nome>/."""
    if nome not in _componentes:
        import streamlit.components.v1 as components

        _componentes[nome] = components.declare_component(
            nome, path=os.path.join(_BASE, nome)
        )
    return _componentes[nome]


def gravar_cantando(
    synced: list[tuple[float, str]],
    audio_data_uri: str | None = None,
    atraso: float = 0.0,
    key: str = "karaoke_rec",
) -> tuple[bytes, str] | None:
    """Toca a base + grava o microfone (com realce da letra). (bytes, mime) ou None."""
    valor = _get_componente("karaoke_rec")(
        synced=[[float(t), str(texto)] for t, texto in synced],
        audio=audio_data_uri,
        atraso=float(atraso),
        key=key,
        default=None,
    )
    return _decode_gravacao(valor)


def gravar_com_video(video_id: str, key: str = "karaoke_yt") -> tuple[bytes, str] | None:
    """Grava o microfone enquanto o vídeo do YouTube toca. (bytes, mime) ou None."""
    valor = _get_componente("karaoke_yt")(video_id=video_id, key=key, default=None)
    return _decode_gravacao(valor)


def _decode_gravacao(valor) -> tuple[bytes, str] | None:
    """Decodifica o dict devolvido pelo componente em (bytes, mimetype)."""
    if not isinstance(valor, dict):
        return None
    b64 = valor.get("audio_b64")
    if not b64:
        return None
    try:
        dados = base64.b64decode(b64)
    except (ValueError, TypeError):
        return None
    if not dados:
        return None
    return dados, valor.get("mime") or "audio/webm"

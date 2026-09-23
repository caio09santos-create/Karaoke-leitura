"""Componente Streamlit bidirecional: toca a base e grava o microfone em um clique.

`declare_component` é preguiçoso para o módulo (e o helper puro `_decode_gravacao`)
poderem ser importados/testados sem o streamlit instalado (ex.: no CI).
"""

import base64
import os

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "karaoke_rec")
_componente = None


def _get_componente():
    global _componente
    if _componente is None:
        import streamlit.components.v1 as components

        _componente = components.declare_component("karaoke_rec", path=_DIR)
    return _componente


def gravar_cantando(
    synced: list[tuple[float, str]],
    audio_data_uri: str | None = None,
    atraso: float = 0.0,
    key: str = "karaoke_rec",
) -> tuple[bytes, str] | None:
    """Renderiza o componente e retorna (bytes, mimetype) da gravação, ou None."""
    valor = _get_componente()(
        synced=[[float(t), str(texto)] for t, texto in synced],
        audio=audio_data_uri,
        atraso=float(atraso),
        key=key,
        default=None,
    )
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

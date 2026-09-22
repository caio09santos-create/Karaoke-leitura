"""Busca de letras na API pública do LRCLIB (https://lrclib.net)."""

import re

import requests

LRCLIB_URL = "https://lrclib.net/api"
HEADERS = {"User-Agent": "karaoke-leitura/1.0 (projeto de estudo)"}


def buscar_letra(artista: str, titulo: str) -> str | None:
    """Retorna a letra da música ou None se não encontrar."""
    try:
        # 1ª tentativa: busca exata por artista + título
        resposta = requests.get(
            f"{LRCLIB_URL}/get",
            params={"artist_name": artista, "track_name": titulo},
            headers=HEADERS,
            timeout=10,
        )
        if resposta.status_code == 200:
            letra = _extrair_letra(resposta.json())
            if letra:
                return letra

        # 2ª tentativa: busca livre
        resposta = requests.get(
            f"{LRCLIB_URL}/search",
            params={"q": f"{artista} {titulo}"},
            headers=HEADERS,
            timeout=10,
        )
        resposta.raise_for_status()
        for item in resposta.json():
            letra = _extrair_letra(item)
            if letra:
                return letra
    except requests.RequestException:
        return None
    return None


def _extrair_letra(dados: dict) -> str | None:
    if dados.get("instrumental"):
        return None
    if dados.get("plainLyrics"):
        return dados["plainLyrics"].strip()
    if dados.get("syncedLyrics"):
        return remover_tempos_lrc(dados["syncedLyrics"])
    return None


def remover_tempos_lrc(texto_lrc: str) -> str:
    """Remove marcações de tempo como [01:23.45] de uma letra sincronizada."""
    linhas = []
    for linha in texto_lrc.splitlines():
        limpa = re.sub(r"\[\d{1,2}:\d{2}(?:[.:]\d{1,3})?\]", "", linha).strip()
        if limpa:
            linhas.append(limpa)
    return "\n".join(linhas)
"""Busca de letras na API pública do LRCLIB (https://lrclib.net)."""

import re

import requests

LRCLIB_URL = "https://lrclib.net/api"
HEADERS = {"User-Agent": "karaoke-leitura/1.0 (projeto de estudo)"}

# Marcação de tempo do LRC, ex.: [01:23.45] ou [01:23.456]
_TEMPO_LRC = r"\[\d{1,2}:\d{2}(?:[.:]\d{1,3})?\]"


def _buscar_dados(artista: str, titulo: str) -> dict | None:
    """Retorna o melhor registro do LRCLIB com letra, preferindo a sincronizada."""
    try:
        # 1ª tentativa: busca exata por artista + título
        resposta = requests.get(
            f"{LRCLIB_URL}/get",
            params={"artist_name": artista, "track_name": titulo},
            headers=HEADERS,
            timeout=10,
        )
        exato = resposta.json() if resposta.status_code == 200 else None
        if exato and _tem_letra(exato) and exato.get("syncedLyrics"):
            return exato  # match exato já com letra sincronizada

        # 2ª tentativa: busca livre (a ordem de artista/título não importa aqui)
        resposta = requests.get(
            f"{LRCLIB_URL}/search",
            params={"q": f"{artista} {titulo}"},
            headers=HEADERS,
            timeout=10,
        )
        resposta.raise_for_status()
        resultados = resposta.json()
        if not isinstance(resultados, list):
            resultados = []
    except requests.RequestException:
        return None

    com_sync = [x for x in resultados if _tem_letra(x) and x.get("syncedLyrics")]
    if com_sync:
        return com_sync[0]
    if exato and _tem_letra(exato):
        return exato
    com_letra = [x for x in resultados if _tem_letra(x)]
    return com_letra[0] if com_letra else None


def buscar_letra(artista: str, titulo: str) -> str | None:
    """Retorna a letra em texto plano da música ou None se não encontrar."""
    dados = _buscar_dados(artista, titulo)
    return _extrair_letra(dados) if dados else None


def buscar_letra_sincronizada(artista: str, titulo: str) -> dict | None:
    """Retorna {"plain", "synced", "artista", "titulo"} do LRCLIB, ou None.

    `artista`/`titulo` vêm do registro do LRCLIB (nomes canônicos), o que corrige
    palpites trocados a partir do título do vídeo. `synced` só vem quando há
    marcação de tempo.
    """
    dados = _buscar_dados(artista, titulo)
    if not dados:
        return None
    plain = _extrair_letra(dados)
    if not plain:
        return None
    synced_raw = None if dados.get("instrumental") else dados.get("syncedLyrics")
    synced = parse_lrc(synced_raw) if synced_raw else None
    return {
        "plain": plain,
        "synced": synced or None,
        "artista": (dados.get("artistName") or artista or "").strip(),
        "titulo": (dados.get("trackName") or titulo or "").strip(),
    }


def _tem_letra(dados: dict) -> bool:
    """True se o registro tem letra aproveitável (não instrumental)."""
    return bool(_extrair_letra(dados))


def _extrair_letra(dados: dict) -> str | None:
    if dados.get("instrumental"):
        return None
    if dados.get("plainLyrics"):
        return dados["plainLyrics"].strip()
    if dados.get("syncedLyrics"):
        return remover_tempos_lrc(dados["syncedLyrics"])
    return None


def parse_lrc(texto_lrc: str) -> list[tuple[float, str]]:
    """Converte uma letra LRC em [(tempo_em_segundos, texto), ...].

    Linhas sem marcação de tempo ou sem texto são ignoradas.
    """
    linhas: list[tuple[float, str]] = []
    for linha in texto_lrc.splitlines():
        m = re.match(r"\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]", linha.strip())
        if not m:
            continue
        minutos, segundos, frac = m.groups()
        tempo = int(minutos) * 60 + int(segundos)
        if frac:
            tempo += int(frac) / (10 ** len(frac))
        texto = re.sub(_TEMPO_LRC, "", linha).strip()
        if texto:
            linhas.append((tempo, texto))
    return linhas


def remover_tempos_lrc(texto_lrc: str) -> str:
    """Remove marcações de tempo como [01:23.45] de uma letra sincronizada."""
    linhas = []
    for linha in texto_lrc.splitlines():
        limpa = re.sub(_TEMPO_LRC, "", linha).strip()
        if limpa:
            linhas.append(limpa)
    return "\n".join(linhas)

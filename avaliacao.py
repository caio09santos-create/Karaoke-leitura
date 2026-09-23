"""Compara a transcrição do canto com a letra e calcula a nota."""

import re
import unicodedata
from difflib import SequenceMatcher
from statistics import median

from rapidfuzz import fuzz


def normalizar_palavra(palavra: str) -> str:
    """Minúsculas, sem acentos e sem pontuação: 'Coração,' -> 'coracao'."""
    palavra = unicodedata.normalize("NFKD", palavra.lower())
    palavra = "".join(c for c in palavra if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", palavra)


def tokenizar(texto: str) -> list[tuple[int, str, str]]:
    """Retorna (número da linha, palavra original, palavra normalizada)."""
    tokens = []
    for n_linha, linha in enumerate(texto.splitlines()):
        # Remove marcações como [Refrão] ou (2x)
        linha = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", linha)
        linha = linha.replace("-", " ")
        for palavra in linha.split():
            normal = normalizar_palavra(palavra)
            if normal:
                tokens.append((n_linha, palavra, normal))
    return tokens


def _tokenizar_hipotese(
    transcricao: str,
    hipotese_tempos: list[tuple[str, float]] | None,
) -> tuple[list[str], list[float | None]]:
    """Constrói (palavras_normalizadas, tempos) da hipótese cantada.

    Se `hipotese_tempos` (lista de (palavra, tempo_seg)) for dada, cada palavra
    da hipótese carrega seu tempo; caso contrário, tokeniza o texto sem tempos.
    """
    if hipotese_tempos is None:
        return [t[2] for t in tokenizar(transcricao)], []
    hip: list[str] = []
    tempos: list[float | None] = []
    for palavra, tempo in hipotese_tempos:
        normal = normalizar_palavra(palavra)
        if normal:
            hip.append(normal)
            tempos.append(tempo)
    return hip, tempos


def avaliar(
    letra: str,
    transcricao: str,
    limiar_semelhanca: int = 80,
    acerto_para_nota_maxima: float = 0.85,
    hipotese_tempos: list[tuple[str, float]] | None = None,
) -> dict:
    """
    Compara palavra a palavra.

    - limiar_semelhanca: palavras com semelhança >= esse valor (0-100)
      contam como acerto (tolera pequenos erros do reconhecimento de voz).
    - acerto_para_nota_maxima: taxa de acerto que já vale nota 100,
      porque o reconhecimento de voz cantada nunca é perfeito.
    - hipotese_tempos: opcional, lista de (palavra, tempo_seg) da transcrição,
      usada só para o feedback por linha (não altera a nota).
    """
    tokens_letra = tokenizar(letra)
    if not tokens_letra:
        raise ValueError("A letra está vazia.")

    ref = [t[2] for t in tokens_letra]
    hip, hip_tempos = _tokenizar_hipotese(transcricao, hipotese_tempos)

    acertos = [False] * len(ref)
    # Para cada palavra da referência acertada, qual índice da hipótese a casou
    # (usado só para estimar o tempo cantado de cada linha).
    hip_de_ref: list[int | None] = [None] * len(ref)
    comparador = SequenceMatcher(None, ref, hip, autojunk=False)
    for tag, i1, i2, j1, j2 in comparador.get_opcodes():
        if tag == "equal":
            for desloc, i in enumerate(range(i1, i2)):
                acertos[i] = True
                hip_de_ref[i] = j1 + desloc
        elif tag == "replace":
            for desloc, i in enumerate(range(i1, i2)):
                j = j1 + desloc
                if j < j2 and fuzz.ratio(ref[i], hip[j]) >= limiar_semelhanca:
                    acertos[i] = True
                    hip_de_ref[i] = j

    total_acertos = sum(acertos)
    taxa = total_acertos / len(ref)
    nota = min(100, round(taxa / acerto_para_nota_maxima * 100))

    # Tempo cantado por palavra da referência (quando há timestamps disponíveis).
    tempos_por_ref: list[float | None] = [
        hip_tempos[j] if (j is not None and j < len(hip_tempos)) else None
        for j in hip_de_ref
    ]

    palavras = [
        (n_linha, original, acertou)
        for (n_linha, original, _), acertou in zip(tokens_letra, acertos, strict=True)
    ]
    return {
        "nota": nota,
        "taxa": taxa,
        "acertos": total_acertos,
        "total": len(ref),
        "palavras": palavras,
        "por_linha": resumo_por_linha(tokens_letra, acertos, tempos_por_ref),
    }


def resumo_por_linha(
    tokens_letra: list[tuple[int, str, str]],
    acertos: list[bool],
    tempos_por_ref: list[float | None] | None = None,
) -> list[dict]:
    """Agrega o resultado por linha da letra.

    Cada item: {linha, texto, palavras=[(original, acertou)], acertos, total,
    taxa, tempo_cantado}. `tempo_cantado` é a mediana dos tempos das palavras
    acertadas da linha, ou None se não houver tempos.
    """
    linhas: dict[int, dict] = {}
    for idx, (n_linha, original, _) in enumerate(tokens_letra):
        info = linhas.setdefault(
            n_linha, {"palavras": [], "acertos": 0, "total": 0, "tempos": []}
        )
        info["palavras"].append((original, acertos[idx]))
        info["total"] += 1
        if acertos[idx]:
            info["acertos"] += 1
        if tempos_por_ref and tempos_por_ref[idx] is not None:
            info["tempos"].append(tempos_por_ref[idx])

    resumo = []
    for n_linha in sorted(linhas):
        info = linhas[n_linha]
        resumo.append(
            {
                "linha": n_linha,
                "texto": " ".join(p for p, _ in info["palavras"]),
                "palavras": info["palavras"],
                "acertos": info["acertos"],
                "total": info["total"],
                "taxa": info["acertos"] / info["total"] if info["total"] else 0.0,
                "tempo_cantado": median(info["tempos"]) if info["tempos"] else None,
            }
        )
    return resumo
